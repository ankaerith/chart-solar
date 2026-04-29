"""RQ worker: consumes the `forecasts` queue and runs the engine pipeline."""

from typing import Any

from rq import Worker, get_current_job

from backend.engine.inputs import ForecastInputs
from backend.engine.pipeline import run_forecast
from backend.infra.logging import configure_logging, get_logger, set_correlation_id
from backend.workers.queue import get_queue, get_redis

log = get_logger(__name__)


def run_forecast_job(payload: dict[str, Any]) -> dict[str, Any]:
    job = get_current_job()
    job_id = job.id if job else None
    set_correlation_id(job.meta.get("correlation_id") if job else None)

    log.info("forecast.start", job_id=job_id)
    inputs = ForecastInputs.model_validate(payload)
    result = run_forecast(inputs)
    log.info("forecast.complete", job_id=job_id)
    return {"artifacts": result.artifacts}


def main() -> None:
    configure_logging("worker")
    worker = Worker([get_queue()], connection=get_redis())
    worker.work()


if __name__ == "__main__":
    main()
