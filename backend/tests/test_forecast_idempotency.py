"""POST /api/forecast: same-input requests reuse the same job_id.

Covers chart-solar-rqax. The endpoint canonicalises the body, scopes
the resulting hash by the caller's user id, and deduplicates re-submits
within the 24h TTL window. Tests run against a real Postgres (the
docker-compose service locally, the `postgres` service container in CI)
because the idempotency primitive lives in SQLAlchemy + Postgres
``ON CONFLICT`` semantics — mocking would just paper over what we want
to verify. Skips when the DB is unreachable so a developer without
compose running can still iterate on other tests.

The forecast queue is mocked: enqueueing is observable via a side-effect
counter, not via a real Redis round-trip. Real-Redis coverage lives in
``test_rq_smoke.py``; this file is purely about the API-layer dedup.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import patch

import asyncpg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, text
from sqlalchemy.exc import OperationalError

import backend.database as _db
from backend.db.models import IdempotencyKey
from backend.entitlements.guards import current_user_id
from backend.main import app


@pytest.fixture(scope="module", autouse=True)
async def _require_postgres() -> None:
    """Skip the module if Postgres is unreachable. Cleanup of the
    ``idempotency_keys`` table is the per-test ``clean_idempotency``
    fixture's job, so this probe stays as cheap as ``SELECT 1``."""
    try:
        async with _db.SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except (OperationalError, asyncpg.exceptions.PostgresError, ConnectionError, OSError) as exc:
        pytest.skip(f"Postgres not reachable at DATABASE_URL: {exc}")


@pytest.fixture
async def clean_idempotency() -> AsyncIterator[None]:
    async with _db.SessionLocal() as session:
        await session.execute(delete(IdempotencyKey))
        await session.commit()
    yield
    async with _db.SessionLocal() as session:
        await session.execute(delete(IdempotencyKey))
        await session.commit()


@pytest.fixture
def fake_enqueue() -> Iterator[list[tuple[str, dict[str, Any]]]]:
    """Capture forecast enqueues without actually pushing onto Redis.

    The endpoint imports ``submit_forecast`` (the service-layer
    trampoline) at module import time, so the patch target is the
    symbol on ``backend.api.forecast`` — patching the service module's
    own re-export would miss the binding the endpoint actually uses.
    """
    captured: list[tuple[str, dict[str, Any]]] = []

    def _capture(job_id: str, payload: dict[str, Any]) -> None:
        captured.append((job_id, payload))

    with patch("backend.api.forecast.submit_forecast", side_effect=_capture):
        yield captured


@pytest.fixture
def client_for_user() -> Iterator[Any]:
    """Yield a factory that builds a TestClient bound to a given user_id.

    Per-user dedup is the whole point of this bead, so every test needs
    to swap user identity cleanly. Overriding the dependency at fixture
    teardown keeps cross-test isolation.
    """
    overrides_to_clear: list[Any] = []

    def _make(user_id: str) -> TestClient:
        app.dependency_overrides[current_user_id] = lambda: user_id
        overrides_to_clear.append(current_user_id)
        return TestClient(app)

    yield _make

    for dep in overrides_to_clear:
        app.dependency_overrides.pop(dep, None)


def _system_inputs(*, dc_kw: float = 8.0) -> dict[str, Any]:
    return {
        "system": {
            "lat": 47.6,
            "lon": -122.3,
            "dc_kw": dc_kw,
            "tilt_deg": 25,
            "azimuth_deg": 180,
        },
        "financial": {},
        "tariff": {"country": "US"},
    }


def test_same_inputs_from_same_user_reuse_job_id(
    clean_idempotency: None,
    fake_enqueue: list[tuple[str, dict[str, Any]]],
    client_for_user: Any,
) -> None:
    client = client_for_user("user-a")
    body = _system_inputs()

    first = client.post("/api/forecast", json=body)
    second = client.post("/api/forecast", json=body)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]
    assert len(fake_enqueue) == 1, "second submission must not enqueue again"


def test_canonical_hash_collapses_numeric_formatting_differences(
    clean_idempotency: None,
    fake_enqueue: list[tuple[str, dict[str, Any]]],
    client_for_user: Any,
) -> None:
    """``5.5`` and ``5.50`` parse to the same float, then re-serialise
    identically through ``canonical_request_hash`` — so the dedup table
    sees them as the same submission."""
    client = client_for_user("user-a")

    raw_first = (
        '{"system":{"lat":47.6,"lon":-122.3,"dc_kw":5.5,"tilt_deg":25,"azimuth_deg":180},'
        '"financial":{},"tariff":{"country":"US"}}'
    )
    raw_second = (
        '{"system":{"lat":47.6,"lon":-122.3,"dc_kw":5.50,"tilt_deg":25,"azimuth_deg":180},'
        '"financial":{},"tariff":{"country":"US"}}'
    )

    headers = {"content-type": "application/json"}
    first = client.post("/api/forecast", content=raw_first, headers=headers)
    second = client.post("/api/forecast", content=raw_second, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["job_id"] == second.json()["job_id"]
    assert len(fake_enqueue) == 1


def test_canonical_hash_collapses_key_ordering_differences(
    clean_idempotency: None,
    fake_enqueue: list[tuple[str, dict[str, Any]]],
    client_for_user: Any,
) -> None:
    """Cosmetic key ordering should not produce a different hash —
    ``canonical_request_hash`` re-serialises with sorted keys before
    hashing."""
    client = client_for_user("user-a")

    body_a = _system_inputs()
    body_b: dict[str, Any] = {
        "tariff": {"country": "US"},
        "financial": {},
        "system": {
            "azimuth_deg": 180,
            "tilt_deg": 25,
            "dc_kw": 8.0,
            "lon": -122.3,
            "lat": 47.6,
        },
    }

    first = client.post("/api/forecast", json=body_a)
    second = client.post("/api/forecast", json=body_b)

    assert first.json()["job_id"] == second.json()["job_id"]
    assert len(fake_enqueue) == 1


def test_different_users_get_different_jobs_for_identical_inputs(
    clean_idempotency: None,
    fake_enqueue: list[tuple[str, dict[str, Any]]],
    client_for_user: Any,
) -> None:
    """User A's submission must not be reused for user B even though
    their bodies hash identically — per-user namespacing is what
    protects users from accidentally inheriting each other's jobs."""
    body = _system_inputs()

    client_a = client_for_user("user-a")
    response_a = client_a.post("/api/forecast", json=body)

    client_b = client_for_user("user-b")
    response_b = client_b.post("/api/forecast", json=body)

    assert response_a.json()["job_id"] != response_b.json()["job_id"]
    assert len(fake_enqueue) == 2


def test_different_inputs_get_different_jobs(
    clean_idempotency: None,
    fake_enqueue: list[tuple[str, dict[str, Any]]],
    client_for_user: Any,
) -> None:
    client = client_for_user("user-a")

    first = client.post("/api/forecast", json=_system_inputs(dc_kw=8.0))
    second = client.post("/api/forecast", json=_system_inputs(dc_kw=10.0))

    assert first.json()["job_id"] != second.json()["job_id"]
    assert len(fake_enqueue) == 2
