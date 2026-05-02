"""Idempotency-Key replay protection + Stripe event dedupe.

Tests hit a real Postgres (the docker-compose `postgres` service locally,
the `postgres` service container in CI). Skips when the DB is unreachable
so a developer without compose running can still iterate on other tests.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta

import asyncpg
import pytest
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError

import backend.database as _db
from backend.db.models import IdempotencyKey, StripeEvent
from backend.infra.idempotency import (
    canonical_request_hash,
    claim_idempotency_slot,
    record_stripe_event,
)
from backend.infra.util import utc_now


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


def test_canonical_hash_is_whitespace_insensitive() -> None:
    a = canonical_request_hash(b'{"a":1,"b":2}')
    b = canonical_request_hash(b'{"b": 2, "a": 1}')
    c = canonical_request_hash(b'{"a":1,"b":3}')
    assert a == b
    assert a != c


def test_canonical_hash_collapses_float_precision() -> None:
    """``5.5`` and ``5.50`` are the same number; both round-trip through
    ``json.loads``/``dumps`` to the same canonical literal."""
    a = canonical_request_hash(b'{"x":5.5}')
    b = canonical_request_hash(b'{"x":5.50}')
    assert a == b


def test_canonical_hash_distinguishes_int_from_float_literal() -> None:
    """``1`` and ``1.0`` are numerically equal but JSON-serialise to
    different literals (``1`` vs ``1.0``); we hash them differently. The
    cost is one duplicate enqueue per literal-style toggle; the worker
    coerces both to the typed Pydantic float anyway."""
    assert canonical_request_hash(b'{"x":1}') != canonical_request_hash(b'{"x":1.0}')


def test_canonical_hash_falls_back_for_non_json() -> None:
    a = canonical_request_hash(b"raw bytes")
    b = canonical_request_hash(b"raw bytes")
    c = canonical_request_hash(b"other")
    assert a == b
    assert a != c


async def test_claim_slot_winner_runs_side_effect(clean_tables: None) -> None:
    async with _db.SessionLocal() as session:
        won, body = await claim_idempotency_slot(
            session,
            route="POST /test",
            key="key-1",
            request_hash="hash-1",
            response_body={"job_id": "job-1"},
        )
    assert won is True
    assert body == {"job_id": "job-1"}


async def test_claim_slot_concurrent_callers_collapse_to_one_winner(
    clean_tables: None,
) -> None:
    """Two parallel claims with the same key — exactly one wins, both
    return the winner's response body."""
    route = "POST /test"
    key = "key-concurrent"

    async def claim(job_id: str) -> tuple[bool, dict[str, object]]:
        async with _db.SessionLocal() as session:
            return await claim_idempotency_slot(
                session,
                route=route,
                key=key,
                request_hash="hash",
                response_body={"job_id": job_id},
            )

    a, b = await asyncio.gather(claim("job-a"), claim("job-b"))
    won_count = sum(1 for w, _ in (a, b) if w)
    assert won_count == 1
    # Both callers see the same job_id (the winner's), regardless of
    # which one of them won the race.
    assert a[1] == b[1]


async def test_claim_slot_treats_expired_winner_as_race_won(clean_tables: None) -> None:
    """If a row is inserted then expires before our follow-up SELECT,
    the helper returns ``(True, our_body)`` so the caller runs the side
    effect — handing the client a cached job_id for a job that never
    ran would be the worst possible outcome.
    """
    route = "POST /test"
    key = "key-expired"
    now = utc_now()

    # Plant an already-expired row (this is the only way to force the
    # race-fallback branch deterministically).
    async with _db.SessionLocal() as session:
        await session.execute(
            IdempotencyKey.__table__.insert().values(
                route=route,
                key=key,
                request_hash="hash-old",
                response_status=200,
                response_body={"job_id": "job-old"},
                created_at=now - timedelta(hours=48),
                expires_at=now - timedelta(seconds=1),
            )
        )
        await session.commit()

    # Now claim — the INSERT loses the conflict (row exists), the SELECT
    # finds nothing non-expired. The fallback should treat this as race-won.
    async with _db.SessionLocal() as session:
        won, body = await claim_idempotency_slot(
            session,
            route=route,
            key=key,
            request_hash="hash-new",
            response_body={"job_id": "job-new"},
            now=now,
        )
    assert won is True
    assert body == {"job_id": "job-new"}


async def test_stripe_replay_records_event_once(clean_tables: None) -> None:
    """A webhook delivered twice must grant the entitlement exactly once."""
    payload = {"id": "evt_123", "type": "checkout.session.completed"}
    grants: list[str] = []

    async def handle(event_id: str, event_type: str, body: dict[str, object]) -> None:
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
