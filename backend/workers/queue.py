"""Redis + RQ. SQS adapter slot is left for the AWS path."""

from functools import lru_cache
from typing import Any

import redis
from rq import Queue
from rq.job import Job

from backend.config import settings


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url)


@lru_cache(maxsize=1)
def get_queue() -> Queue:
    return Queue("forecasts", connection=get_redis())


def enqueue_forecast(job_id: str, payload: dict[str, Any]) -> None:
    from backend.workers.forecast_worker import run_forecast_job

    get_queue().enqueue(run_forecast_job, payload, job_id=job_id)


def get_job(job_id: str) -> Job | None:
    try:
        return Job.fetch(job_id, connection=get_redis())
    except Exception:
        return None
