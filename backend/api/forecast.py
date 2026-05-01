"""Forecast submission + status endpoints.

POST /api/forecast is body-derived idempotent: the canonical SHA-256 of
the JSON body, namespaced by the caller's user id, deduplicates same-input
re-submissions to a single queued job. Two requests with the same inputs
in a 24h window return the same ``job_id``; the engine never runs twice.

Per-user namespacing means user A's inputs cannot short-circuit user B's
identical inputs — they go to separate slots even though their bodies
hash the same. The user-id placeholder (``current_user_id``) returns
``"anonymous"`` until auth lands; tests override the dependency to
simulate distinct callers.

Reference: docs/ENGINEERING.md § Operational expectations; chart-solar-rqax.
"""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

import backend.database as _db
from backend.engine.inputs import ForecastInputs
from backend.entitlements.guards import current_user_id
from backend.infra.idempotency import (
    canonical_request_hash,
    claim_idempotency_slot,
)
from backend.infra.logging import get_logger
from backend.services.forecast_service import get_forecast_job, submit_forecast

router = APIRouter()
log = get_logger(__name__)

#: Stable route key for the idempotency table. Decoupled from the URL
#: path so a future route refactor doesn't silently invalidate live
#: cache entries.
FORECAST_ROUTE_KEY = "POST /api/forecast"


@router.post("/forecast")
async def submit_forecast_endpoint(
    request: Request,
    inputs: ForecastInputs,
    user_id: str = Depends(current_user_id),
) -> dict[str, Any]:
    """Submit a forecast job; reuse an existing job_id when the same
    user has already submitted these exact inputs in the last 24h.

    The body is hashed canonically (sorted keys, normalised numeric
    formats) so semantic-no-op formatting differences — ``5.5`` vs
    ``5.50``, key reordering, whitespace — collapse to the same job.
    Concurrent same-input submissions race-claim the slot via
    ``claim_idempotency_slot`` (INSERT … ON CONFLICT) and only the
    winning request enqueues; losers return the winner's job_id.
    """
    body = await request.body()
    body_hash = canonical_request_hash(body)
    namespaced_key = f"{user_id}:{body_hash}"

    job_id = str(uuid4())
    candidate_response: dict[str, Any] = {"job_id": job_id, "status": "queued"}

    async with _db.SessionLocal() as session:
        won, response_body = await claim_idempotency_slot(
            session,
            route=FORECAST_ROUTE_KEY,
            key=namespaced_key,
            request_hash=body_hash,
            response_body=candidate_response,
        )

    if not won:
        log.info(
            "forecast.idempotent_replay",
            user_id=user_id,
            cached_job_id=response_body["job_id"],
        )
        return response_body

    submit_forecast(job_id, inputs.model_dump())
    log.info("forecast.enqueued", job_id=job_id, user_id=user_id)
    return response_body


@router.get("/forecast/{job_id}")
async def forecast_status(job_id: str) -> dict[str, Any]:
    view = get_forecast_job(job_id)
    if view is None:
        raise HTTPException(status_code=404, detail="job not found")
    response: dict[str, Any] = {"job_id": view.job_id, "status": view.status}
    if view.result is not None:
        response["result"] = view.result
    if view.error is not None:
        response["error"] = view.error
    return response
