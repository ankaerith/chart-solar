"""Redis + RQ end-to-end round-trip.

Skips locally when Redis isn't running; CI exercises it via a `redis` service container.
"""

from collections.abc import Iterator
from uuid import uuid4

import pytest
import redis as redis_lib
from rq import Queue, SimpleWorker
from rq.job import Job, JobStatus

from backend.engine.inputs import (
    FinancialInputs,
    ForecastInputs,
    SystemInputs,
    TariffInputs,
)
from backend.workers.queue import enqueue_forecast, get_queue, get_redis


@pytest.fixture(scope="module", autouse=True)
def _require_redis() -> None:
    try:
        get_redis().ping()
    except redis_lib.exceptions.ConnectionError:
        pytest.skip("Redis not reachable at REDIS_URL — start `docker compose up redis` to enable")


@pytest.fixture
def queue() -> Iterator[Queue]:
    q = get_queue()
    q.empty()  # type: ignore[no-untyped-call]
    yield q
    q.empty()  # type: ignore[no-untyped-call]


def test_forecast_job_round_trips_through_real_queue(queue: Queue) -> None:
    inputs = ForecastInputs(
        system=SystemInputs(lat=47.6, lon=-122.3, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(),
        tariff=TariffInputs(country="US"),
    )
    job_id = str(uuid4())

    enqueue_forecast(job_id, inputs.model_dump())

    worker = SimpleWorker([queue], connection=get_redis())
    worker.work(burst=True, with_scheduler=False)

    job = Job.fetch(job_id, connection=get_redis())
    assert job.get_status() == JobStatus.FINISHED
    assert job.result == {"artifacts": {}}
