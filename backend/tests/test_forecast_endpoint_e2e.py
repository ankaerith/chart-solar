"""End-to-end HTTP → RQ → HTTP smoke (chart-solar-zyf).

Exercises the full forecast lifecycle through the real public surface:

* HTTP POST /api/forecast → returns ``{job_id, status: queued}``
* RQ worker drains the queue in burst mode
* HTTP GET /api/forecast/{job_id} → returns ``{job_id, status: done, result}``

Pre-existing tests cover slices of this:

* ``test_rq_smoke.py`` exercises queue → worker → ``Job.fetch`` directly,
  bypassing the HTTP surface.
* ``test_forecast_idempotency.py`` exercises POST dedup with the queue
  patched out.

This file is the seam between them — the only place we assert that the
GET endpoint normalises RQ's status names into the contract's
``queued|running|done|error`` vocabulary, and that ``result`` is wired
through to the response body.

Requires both Redis and Postgres (idempotency claim hits Postgres
before enqueueing, worker round-trip needs Redis). Skips when either
is unreachable so a developer with only one service running can still
work on adjacent code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import asyncpg
import pytest
import redis as redis_lib
from fastapi.testclient import TestClient
from rq import SimpleWorker
from sqlalchemy import delete, text
from sqlalchemy.exc import OperationalError

import backend.database as _db
import backend.workers.forecast_worker as forecast_worker
from backend.db.models import IdempotencyKey
from backend.engine.inputs import ForecastInputs
from backend.entitlements.guards import current_user_id
from backend.main import app
from backend.providers.fake import synthetic_tmy
from backend.providers.irradiance import TmyData
from backend.workers.queue import get_queue, get_redis


@pytest.fixture(scope="module", autouse=True)
def _require_redis() -> None:
    try:
        get_redis().ping()
    except redis_lib.exceptions.ConnectionError:
        pytest.skip("Redis not reachable at REDIS_URL — start `docker compose up redis` to enable")


@pytest.fixture(scope="module", autouse=True)
async def _require_postgres() -> None:
    try:
        async with _db.SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except (OperationalError, asyncpg.exceptions.PostgresError, ConnectionError, OSError) as exc:
        pytest.skip(f"Postgres not reachable at DATABASE_URL: {exc}")


@pytest.fixture
def empty_queue() -> Iterator[None]:
    q = get_queue()
    q.empty()  # type: ignore[no-untyped-call]
    yield
    q.empty()  # type: ignore[no-untyped-call]


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
def _stub_tmy_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use synthetic clear-sky TMY in-process — same trick as test_rq_smoke.

    SimpleWorker runs jobs in this process, so the patched module-level
    ``_fetch_tmy`` is what the worker sees too.
    """

    def _fake(inputs: ForecastInputs) -> TmyData:
        return synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    monkeypatch.setattr(forecast_worker, "_fetch_tmy", _fake)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A TestClient bound to a stable user id so the per-user idempotency
    namespace is predictable across requests in a single test."""
    app.dependency_overrides[current_user_id] = lambda: "e2e-test-user"
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(current_user_id, None)


def _baseline_body() -> dict[str, Any]:
    return {
        "system": {
            "lat": 47.6,
            "lon": -122.3,
            "dc_kw": 8.0,
            "tilt_deg": 25,
            "azimuth_deg": 180,
        },
        "financial": {},
        "tariff": {"country": "US"},
    }


def test_post_then_drain_then_get_returns_done_with_result(
    client: TestClient,
    clean_idempotency: None,
    empty_queue: None,
    _stub_tmy_fetch: None,
) -> None:
    """Golden path: POST → 202-ish queued → worker drains → GET returns
    status=done with the engine artifacts payload. Asserts the GET
    payload shape that the wizard will consume."""
    submit = client.post("/api/forecast", json=_baseline_body())
    assert submit.status_code == 200
    body = submit.json()
    job_id = body["job_id"]
    assert body["status"] == "queued"

    # Drain the queue synchronously in this process. SimpleWorker runs
    # jobs in-thread so the test stays deterministic.
    SimpleWorker([get_queue()], connection=get_redis()).work(burst=True, with_scheduler=False)

    poll = client.get(f"/api/forecast/{job_id}")
    assert poll.status_code == 200
    polled = poll.json()
    assert polled["job_id"] == job_id
    assert polled["status"] == "done"
    artifacts = polled["result"]["artifacts"]
    # Without a tariff schedule the chain runs irradiance → consumption
    # → dc_production → degradation and stops; the GET payload must
    # carry those artifact keys verbatim so the wizard can render
    # "estimated annual production" without a separate roundtrip.
    assert "engine.dc_production" in artifacts
    assert "engine.degradation" in artifacts


def test_get_unknown_job_returns_404(client: TestClient) -> None:
    """A poll for an id we never enqueued must 404 rather than silently
    returning ``status=queued`` (which would lie to the client)."""
    response = client.get("/api/forecast/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_get_before_drain_returns_queued(
    client: TestClient,
    clean_idempotency: None,
    empty_queue: None,
) -> None:
    """A poll *before* any worker has drained the queue must report
    ``queued`` (not ``running`` or ``done``). This pins the contract
    that polling is safe at any time after submission."""
    submit = client.post("/api/forecast", json=_baseline_body())
    job_id = submit.json()["job_id"]

    poll = client.get(f"/api/forecast/{job_id}")
    assert poll.status_code == 200
    polled = poll.json()
    assert polled["status"] == "queued"
    # No result key for non-done jobs — the contract reserves it for
    # done responses so callers can pattern-match on its presence.
    assert "result" not in polled
