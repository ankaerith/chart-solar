"""Redis + RQ end-to-end round-trip.

Skips locally when Redis isn't running; CI exercises it via a `redis` service container.
"""

from collections.abc import Iterator
from uuid import uuid4

import pytest
import redis as redis_lib
from rq import Queue, SimpleWorker
from rq.job import Job, JobStatus

import backend.workers.forecast_worker as forecast_worker
from backend.engine.inputs import (
    FinancialInputs,
    ForecastInputs,
    SystemInputs,
    TariffInputs,
)
from backend.infra.logging import set_correlation_id
from backend.providers.fake import synthetic_tmy
from backend.providers.irradiance import TmyData
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


@pytest.fixture
def _stub_tmy_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the worker's TMY fetcher for a synthetic clear-sky year.

    ``SimpleWorker`` runs jobs in-process, so monkeypatching the module
    attribute on the test process also patches the worker's view. The
    real fetcher hits NSRDB / PVGIS and needs API keys + network — both
    absent in CI.
    """

    def _fake(inputs: ForecastInputs) -> TmyData:
        return synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    monkeypatch.setattr(forecast_worker, "_fetch_tmy", _fake)


def test_forecast_job_round_trips_through_real_queue(queue: Queue, _stub_tmy_fetch: None) -> None:
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
    artifacts = job.result["artifacts"]
    # Without a tariff schedule or export-credit config the chain runs
    # the always-on physics steps and stops before billing.
    assert "engine.dc_production" in artifacts
    assert "engine.degradation" in artifacts
    assert "engine.tariff" not in artifacts
    assert "engine.export_credit" not in artifacts


def test_correlation_id_propagates_to_job_meta(queue: Queue) -> None:
    inputs = ForecastInputs(
        system=SystemInputs(lat=47.6, lon=-122.3, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(),
        tariff=TariffInputs(country="US"),
    )
    job_id = str(uuid4())

    set_correlation_id("test-corr-id-xyz")
    try:
        enqueue_forecast(job_id, inputs.model_dump())
    finally:
        set_correlation_id(None)

    job = Job.fetch(job_id, connection=get_redis())
    assert job.meta["correlation_id"] == "test-corr-id-xyz"
