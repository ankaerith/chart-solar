"""Redis + RQ. SQS adapter slot is left for the AWS path."""

import asyncio
from functools import lru_cache
from typing import Any

import redis
from rq import Queue, Retry
from rq.exceptions import NoSuchJobError
from rq.job import Job

from backend.config import settings
from backend.infra.logging import get_correlation_id

#: Hard cap on wall-clock time for a single forecast job. Engine + TMY
#: fetch should land inside one minute; 5× headroom guards against
#: pathological provider latency without leaking workers.
FORECAST_JOB_TIMEOUT_SECONDS = 300

#: How long Redis retains a finished job's return value. Aligns with the
#: 24h POST idempotency window so resubmissions can fetch the cached
#: result by job_id.
FORECAST_RESULT_TTL_SECONDS = 24 * 60 * 60

#: How long Redis retains a failed job's traceback + metadata. Matched to
#: result_ttl so debug context survives the same window as success rows.
FORECAST_FAILURE_TTL_SECONDS = 24 * 60 * 60

#: Retry budget for transient upstream failures (TMY provider 5xx /
#: rate limits). Two retries with an escalating backoff covers most
#: provider blips without masking real outages.
FORECAST_RETRY_INTERVALS_SECONDS = (10, 30)


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url)


@lru_cache(maxsize=1)
def get_queue() -> Queue:
    return Queue("forecasts", connection=get_redis())


def _enqueue_forecast_sync(job_id: str, payload: dict[str, Any], owner_user_id: str) -> None:
    from backend.workers.forecast_worker import run_forecast_job

    get_queue().enqueue(
        run_forecast_job,
        payload,
        job_id=job_id,
        meta={"correlation_id": get_correlation_id(), "owner_user_id": owner_user_id},
        job_timeout=FORECAST_JOB_TIMEOUT_SECONDS,
        result_ttl=FORECAST_RESULT_TTL_SECONDS,
        failure_ttl=FORECAST_FAILURE_TTL_SECONDS,
        retry=Retry(
            max=len(FORECAST_RETRY_INTERVALS_SECONDS),
            interval=list(FORECAST_RETRY_INTERVALS_SECONDS),
        ),
    )


async def enqueue_forecast(job_id: str, payload: dict[str, Any], owner_user_id: str) -> None:
    """Enqueue a forecast job with the standard timeout / TTL / retry
    policy. The request's correlation ID is stamped into job meta so
    worker log lines correlate with the originating HTTP request even
    though they execute in a different process; ``owner_user_id`` is
    also stamped into meta so ``GET /api/forecast/{job_id}`` can
    enforce that the polling caller actually submitted the job.

    The redis-py client used here is synchronous; the LPUSH is offloaded
    via ``asyncio.to_thread`` so a Redis stall can't block the API event
    loop.
    """
    await asyncio.to_thread(_enqueue_forecast_sync, job_id, payload, owner_user_id)


def get_job(job_id: str) -> Job | None:
    """Fetch an RQ job by id, or ``None`` if the job has aged out / never existed.

    Only ``NoSuchJobError`` collapses to ``None``. Redis connection
    errors and other infrastructure failures propagate so the API surfaces
    a 5xx with structured logs instead of a misleading 404.
    """
    try:
        return Job.fetch(job_id, connection=get_redis())
    except NoSuchJobError:
        return None
