from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from backend.engine.inputs import ForecastInputs
from backend.infra.logging import get_logger
from backend.workers.queue import enqueue_forecast, get_job

router = APIRouter()
log = get_logger(__name__)


@router.post("/forecast")
async def submit_forecast(inputs: ForecastInputs) -> dict[str, Any]:
    job_id = str(uuid4())
    enqueue_forecast(job_id, inputs.model_dump())
    log.info("forecast.enqueued", job_id=job_id)
    return {"job_id": job_id, "status": "queued"}


@router.get("/forecast/{job_id}")
async def forecast_status(job_id: str) -> dict[str, Any]:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, "status": job.get_status(), "result": job.result}
