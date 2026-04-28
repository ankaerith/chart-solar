"""RQ worker: consumes the `forecasts` queue and runs the engine pipeline."""

import sys
from typing import Any

from rq import Worker

from backend.engine.inputs import ForecastInputs
from backend.engine.pipeline import run_forecast
from backend.workers.queue import get_queue, get_redis


def run_forecast_job(payload: dict[str, Any]) -> dict[str, Any]:
    inputs = ForecastInputs.model_validate(payload)
    result = run_forecast(inputs)
    return {"artifacts": result.artifacts}


def main() -> None:
    worker = Worker([get_queue()], connection=get_redis())
    worker.work()


if __name__ == "__main__":
    main()
    sys.exit(0)
