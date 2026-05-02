"""Forecast queue + status orchestration.

The HTTP route shapes the request, hashes the body, and claims the
idempotency slot; everything past that — handing the payload to the
queue, fetching the job back, and translating RQ's internal status
vocabulary into the four states (``queued`` / ``running`` / ``done``
/ ``error``) the API contract exposes — lives here. That keeps
``backend.api`` free of any direct ``backend.workers`` import.

The status translator is intentionally service-layer code, not
api-layer: tomorrow we may swap RQ for SQS or Cloud Tasks, and the
``deferred`` / ``scheduled`` / ``created`` ⇒ ``queued`` collapse will
be different on the new backend. The API contract stays put.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from rq.job import JobStatus

from backend.workers.queue import enqueue_forecast as _enqueue_forecast
from backend.workers.queue import get_job as _get_job

#: The four-state vocabulary the API contract exposes.
ApiStatus = Literal["queued", "running", "done", "error"]

#: Map RQ's internal job states onto the four-state vocabulary the API
#: contract exposes. ``deferred`` / ``scheduled`` / ``created`` collapse
#: onto ``queued`` — all three mean "the engine hasn't started", which
#: is what the caller actually needs to know. ``stopped`` / ``canceled``
#: surface as ``error`` so the UI tells the user the job won't complete;
#: the operator who killed it has the audit trail.
_RQ_STATUS_TO_API_STATUS: dict[JobStatus, ApiStatus] = {
    JobStatus.CREATED: "queued",
    JobStatus.QUEUED: "queued",
    JobStatus.DEFERRED: "queued",
    JobStatus.SCHEDULED: "queued",
    JobStatus.STARTED: "running",
    JobStatus.FINISHED: "done",
    JobStatus.FAILED: "error",
    JobStatus.STOPPED: "error",
    JobStatus.CANCELED: "error",
}


@dataclass(frozen=True)
class ForecastJobView:
    """API-facing snapshot of a forecast job's state.

    ``result`` is set when ``status == "done"`` — the engine artifacts
    payload returned by the worker. ``error`` carries RQ's serialised
    traceback when ``status == "error"`` so the caller self-diagnoses
    without grepping worker logs. ``owner_user_id`` is the user id that
    submitted the job (stamped into RQ meta at enqueue time); the API
    route uses it to refuse polls from anyone else.
    """

    job_id: str
    status: ApiStatus
    owner_user_id: str | None
    result: Any | None = None
    error: str | None = None


async def submit_forecast(job_id: str, payload: dict[str, Any], owner_user_id: str) -> None:
    """Hand a forecast job off to the queue under the given ``job_id``.

    Trampoline to ``backend.workers.queue.enqueue_forecast`` — the
    indirection is the point: ``backend.api.forecast`` calls this
    instead of reaching into the worker package. Any future change in
    queue technology (SQS, Cloud Tasks) lands inside ``workers/`` and
    this signature absorbs the difference.

    ``owner_user_id`` is stamped into RQ job meta so subsequent
    ``GET /api/forecast/{job_id}`` requests can verify the polling
    caller is the one that submitted.

    Async because the underlying ``redis-py`` client is synchronous and
    the worker queue offloads it via ``asyncio.to_thread``; awaiting here
    keeps the behaviour consistent and lets the API route ``await`` directly.
    """
    await _enqueue_forecast(job_id, payload, owner_user_id)


def get_forecast_job(job_id: str) -> ForecastJobView | None:
    """Look up a forecast job's API-facing state, or return ``None`` when
    the job isn't known to the queue (expired or never submitted).

    Folds the RQ ``JobStatus`` vocabulary into the four contract states
    here so the API route never sees an RQ-specific symbol. Result and
    error fields are populated only when the corresponding terminal
    state is reached. ``owner_user_id`` rides through from RQ meta so
    the route layer can enforce ownership before returning the result.
    """
    job = _get_job(job_id)
    if job is None:
        return None
    api_status = _RQ_STATUS_TO_API_STATUS[JobStatus(job.get_status())]
    owner = job.meta.get("owner_user_id") if job.meta else None
    if api_status == "done":
        return ForecastJobView(
            job_id=job_id, status=api_status, owner_user_id=owner, result=job.result
        )
    if api_status == "error":
        return ForecastJobView(
            job_id=job_id, status=api_status, owner_user_id=owner, error=job.exc_info
        )
    return ForecastJobView(job_id=job_id, status=api_status, owner_user_id=owner)


__all__ = [
    "ForecastJobView",
    "get_forecast_job",
    "submit_forecast",
]
