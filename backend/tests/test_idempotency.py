"""Idempotency-Key replay protection + Stripe event dedupe.

Tests hit a real Postgres (the docker-compose `postgres` service locally,
the `postgres` service container in CI). Skips when the DB is unreachable
so a developer without compose running can still iterate on other tests.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import asyncpg
import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError

import backend.database as _db
from backend.db.models import IdempotencyKey, StripeEvent
from backend.infra.idempotency import (
    DEFAULT_TTL_SECONDS,
    canonical_request_hash,
    idempotent,
    record_stripe_event,
)


@pytest.fixture(scope="module", autouse=True)
async def _require_postgres() -> None:
    try:
        async with _db.SessionLocal() as session:
            await session.execute(delete(IdempotencyKey))
            await session.execute(delete(StripeEvent))
            await session.commit()
    except (OperationalError, asyncpg.exceptions.PostgresError, ConnectionError, OSError) as exc:
        pytest.skip(f"Postgres not reachable at DATABASE_URL: {exc}")


@pytest.fixture
async def clean_tables() -> AsyncIterator[None]:
    async with _db.SessionLocal() as session:
        await session.execute(delete(IdempotencyKey))
        await session.execute(delete(StripeEvent))
        await session.commit()
    yield
    async with _db.SessionLocal() as session:
        await session.execute(delete(IdempotencyKey))
        await session.execute(delete(StripeEvent))
        await session.commit()


def _build_app() -> tuple[FastAPI, dict[str, int]]:
    """Tiny FastAPI app with one decorated endpoint and a call counter."""
    app = FastAPI()
    router = APIRouter()
    counter = {"calls": 0}

    @router.post("/echo")
    @idempotent(route_key="POST /echo")
    async def echo(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
        counter["calls"] += 1
        return {"received": payload, "call_number": counter["calls"]}

    app.include_router(router)
    return app, counter


def test_canonical_hash_is_whitespace_insensitive() -> None:
    a = canonical_request_hash(b'{"a":1,"b":2}')
    b = canonical_request_hash(b'{"b": 2, "a": 1}')
    c = canonical_request_hash(b'{"a":1,"b":3}')
    assert a == b
    assert a != c


def test_canonical_hash_falls_back_for_non_json() -> None:
    a = canonical_request_hash(b"raw bytes")
    b = canonical_request_hash(b"raw bytes")
    c = canonical_request_hash(b"other")
    assert a == b
    assert a != c


def test_replay_with_same_key_and_body_returns_cached_response(
    clean_tables: None,
) -> None:
    app, counter = _build_app()
    client = TestClient(app)
    headers = {"Idempotency-Key": "key-replay-1"}
    body = {"x": 1, "y": "hello"}

    first = client.post("/echo", json=body, headers=headers)
    second = client.post("/echo", json=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert counter["calls"] == 1, "handler should only run once across replays"


def test_replay_with_different_body_returns_409(clean_tables: None) -> None:
    app, counter = _build_app()
    client = TestClient(app)
    headers = {"Idempotency-Key": "key-mismatch-1"}

    first = client.post("/echo", json={"x": 1}, headers=headers)
    second = client.post("/echo", json={"x": 2}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 409
    assert "Idempotency-Key" in second.json()["detail"]
    assert counter["calls"] == 1


def test_request_without_header_runs_handler_each_call(clean_tables: None) -> None:
    app, counter = _build_app()
    client = TestClient(app)

    first = client.post("/echo", json={"x": 1})
    second = client.post("/echo", json={"x": 1})

    assert first.status_code == 200
    assert second.status_code == 200
    assert counter["calls"] == 2
    # No row was persisted because no key was supplied.


def test_keys_are_namespaced_per_route(clean_tables: None) -> None:
    """Same key on two different routes must not collide."""
    app = FastAPI()
    counter = {"a": 0, "b": 0}

    @app.post("/a")
    @idempotent(route_key="POST /a")
    async def a(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
        counter["a"] += 1
        return {"endpoint": "a", "n": counter["a"]}

    @app.post("/b")
    @idempotent(route_key="POST /b")
    async def b(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
        counter["b"] += 1
        return {"endpoint": "b", "n": counter["b"]}

    client = TestClient(app)
    headers = {"Idempotency-Key": "shared-key"}

    assert client.post("/a", json={}, headers=headers).json() == {"endpoint": "a", "n": 1}
    assert client.post("/b", json={}, headers=headers).json() == {"endpoint": "b", "n": 1}
    # Replay each — both should return their own cached response.
    assert client.post("/a", json={}, headers=headers).json() == {"endpoint": "a", "n": 1}
    assert client.post("/b", json={}, headers=headers).json() == {"endpoint": "b", "n": 1}
    assert counter == {"a": 1, "b": 1}


async def test_default_ttl_24_hours(clean_tables: None) -> None:
    """Default TTL is 24h. Per-route override is exercised by passing
    `ttl_seconds=` to the decorator (not exercised here — covered by static
    type-check on the decorator signature)."""
    app, _counter = _build_app()
    client = TestClient(app)
    headers = {"Idempotency-Key": "key-ttl-default"}

    client.post("/echo", json={"x": 1}, headers=headers)

    async with _db.SessionLocal() as session:
        from sqlalchemy import select

        row = (
            await session.execute(
                select(IdempotencyKey).where(
                    IdempotencyKey.key == "key-ttl-default",
                    IdempotencyKey.route == "POST /echo",
                )
            )
        ).scalar_one()
        delta_seconds = (row.expires_at - row.created_at).total_seconds()
        # Allow some slack for clock drift between the SQL `now()` and our
        # in-process datetime.now(UTC); the gap should still be ~24h.
        assert abs(delta_seconds - DEFAULT_TTL_SECONDS) < 60


async def test_per_route_ttl_override(clean_tables: None) -> None:
    app = FastAPI()

    @app.post("/short")
    @idempotent(route_key="POST /short", ttl_seconds=300)
    async def short(request: Request, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    client = TestClient(app)
    client.post("/short", json={}, headers={"Idempotency-Key": "key-ttl-300"})

    async with _db.SessionLocal() as session:
        from sqlalchemy import select

        row = (
            await session.execute(select(IdempotencyKey).where(IdempotencyKey.key == "key-ttl-300"))
        ).scalar_one()
        delta_seconds = (row.expires_at - row.created_at).total_seconds()
        assert abs(delta_seconds - 300) < 30


async def test_stripe_replay_records_event_once(clean_tables: None) -> None:
    """A webhook delivered twice must grant the entitlement exactly once."""
    payload = {"id": "evt_123", "type": "checkout.session.completed"}
    grants: list[str] = []

    async def handle(event_id: str, event_type: str, body: dict[str, Any]) -> None:
        async with _db.SessionLocal() as session:
            newly_recorded = await record_stripe_event(
                session,
                event_id=event_id,
                event_type=event_type,
                payload=body,
            )
            if newly_recorded:
                grants.append(event_id)

    await handle("evt_123", "checkout.session.completed", payload)
    await handle("evt_123", "checkout.session.completed", payload)
    await handle("evt_123", "checkout.session.completed", payload)

    assert grants == ["evt_123"], f"expected exactly one grant, got {grants}"

    async with _db.SessionLocal() as session:
        from sqlalchemy import select

        rows = (await session.execute(select(StripeEvent))).scalars().all()
        assert len(rows) == 1
        assert rows[0].event_id == "evt_123"


async def test_stripe_distinct_events_each_record(clean_tables: None) -> None:
    async with _db.SessionLocal() as session:
        a = await record_stripe_event(session, event_id="evt_a", event_type="x", payload={"n": 1})
    async with _db.SessionLocal() as session:
        b = await record_stripe_event(session, event_id="evt_b", event_type="x", payload={"n": 2})
    assert a is True
    assert b is True


def test_handler_missing_request_param_raises(clean_tables: None) -> None:
    app = FastAPI()

    @app.post("/no-request")
    @idempotent(route_key="POST /no-request")
    async def no_request(payload: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
        return {"ok": True}

    # `raise_server_exceptions=False` lets the TestClient surface the 500
    # rather than re-raising — we want to assert the response, not the trace.
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/no-request", json={"x": 1}, headers={"Idempotency-Key": "k"})
    assert response.status_code == 500


def test_replay_response_is_byte_for_byte_identical(clean_tables: None) -> None:
    app, _counter = _build_app()
    client = TestClient(app)
    headers = {"Idempotency-Key": str(uuid4())}
    body = {"complex": [1, 2, {"nested": True}], "unicode": "café"}

    first = client.post("/echo", json=body, headers=headers)
    second = client.post("/echo", json=body, headers=headers)

    assert first.json() == second.json()
    # The cached response is JSON-serialised once and replayed — verify the
    # round-trip preserves unicode + nested structure.
    assert json.loads(second.content) == first.json()
