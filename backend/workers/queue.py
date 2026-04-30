"""Redis + RQ. SQS adapter slot is left for the AWS path.

Job lifecycle policy (chart-solar-zyf):

* ``job_timeout`` — 5 minutes. The engine pipeline + a real TMY fetch
  (NSRDB / PVGIS / Open-Meteo) lands well inside one minute on the
  reference 8 kW system; 5 minutes leaves headroom for cold caches and
  retried provider responses without letting a stuck job tie up a
  worker indefinitely.
* ``result_ttl`` — 24 hours. Matches the POST /api/forecast idempotency
  window: a same-input resubmission within 24h must be able to fetch
  the cached result by ``job_id`` rather than re-running the engine.
  After 24h the result expires and the next POST starts a fresh job.
* ``failure_ttl`` — 24 hours. Failed jobs are kept long enough for an
  oncall engineer to inspect the traceback + correlation id; after that
  they roll off automatically. Resubmitting an identical request after
  failure_ttl elapses re-runs (the idempotency row also expires).
* ``retry`` — RQ ``Retry(max=2, interval=[10, 30])``. TMY fetches hit
  external providers that occasionally rate-limit or return transient
  500s; two short re-tries cover the common case without hiding a
  genuine outage. The engine math itself is deterministic, so once
  the upstream call succeeds the retry budget is essentially never
  consumed for engine reasons.
"""

from functools import lru_cache
from typing import Any

import redis
from rq import Queue, Retry
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


def enqueue_forecast(job_id: str, payload: dict[str, Any]) -> None:
    """Enqueue a forecast job with the standard timeout / TTL / retry
    policy and the active correlation ID stamped into job meta.

    The correlation ID is read at enqueue time from contextvars and
    stored on ``job.meta``; the worker reads it back in
    ``run_forecast_job`` so log lines from the worker correlate with
    the originating HTTP request even though they execute in a
    different process.
    """
    from backend.workers.forecast_worker import run_forecast_job

    get_queue().enqueue(
        run_forecast_job,
        payload,
        job_id=job_id,
        meta={"correlation_id": get_correlation_id()},
        job_timeout=FORECAST_JOB_TIMEOUT_SECONDS,
        result_ttl=FORECAST_RESULT_TTL_SECONDS,
        failure_ttl=FORECAST_FAILURE_TTL_SECONDS,
        retry=Retry(
            max=len(FORECAST_RETRY_INTERVALS_SECONDS),
            interval=list(FORECAST_RETRY_INTERVALS_SECONDS),
        ),
    )


def get_job(job_id: str) -> Job | None:
    try:
        return Job.fetch(job_id, connection=get_redis())
    except Exception:
        return None
