"""Forecast service translates RQ JobStatus into the API contract.

These tests pin the four-state mapping and result/error attachment so
a future queue-backend swap (SQS, Cloud Tasks) keeps the same surface
even when its native job-status vocabulary differs.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from rq.job import JobStatus

from backend.services.forecast_service import (
    ForecastJobView,
    get_forecast_job,
)


def _fake_job(
    status: JobStatus,
    *,
    result: Any = None,
    exc_info: str | None = None,
    owner_user_id: str | None = "anonymous",
) -> MagicMock:
    job = MagicMock()
    job.get_status.return_value = status.value
    job.result = result
    job.exc_info = exc_info
    job.meta = {"owner_user_id": owner_user_id} if owner_user_id is not None else {}
    return job


def test_get_forecast_job_returns_none_when_queue_has_no_record() -> None:
    """Expired or never-submitted job_ids surface as ``None`` so the
    route can map it to a 404 without leaking RQ-specific errors."""
    with patch("backend.services.forecast_service._get_job", return_value=None):
        assert get_forecast_job("missing") is None


def test_finished_status_collapses_to_done_with_result() -> None:
    expected_result = {"npv": 12345.0}
    job = _fake_job(JobStatus.FINISHED, result=expected_result)
    with patch("backend.services.forecast_service._get_job", return_value=job):
        view = get_forecast_job("job-1")
    assert view == ForecastJobView(
        job_id="job-1", status="done", owner_user_id="anonymous", result=expected_result
    )


def test_failed_status_collapses_to_error_with_traceback() -> None:
    job = _fake_job(JobStatus.FAILED, exc_info="Traceback (most recent call last):\n …\n")
    with patch("backend.services.forecast_service._get_job", return_value=job):
        view = get_forecast_job("job-2")
    assert view is not None
    assert view.status == "error"
    assert view.error is not None and "Traceback" in view.error
    assert view.result is None


def test_started_status_maps_to_running_without_result_or_error() -> None:
    job = _fake_job(JobStatus.STARTED)
    with patch("backend.services.forecast_service._get_job", return_value=job):
        view = get_forecast_job("job-3")
    assert view == ForecastJobView(job_id="job-3", status="running", owner_user_id="anonymous")


def test_pre_start_states_collapse_to_queued() -> None:
    """``deferred`` / ``scheduled`` / ``created`` / ``queued`` all mean
    "engine hasn't started" — the API contract surfaces just one
    pre-start state, ``queued``."""
    for native in (JobStatus.CREATED, JobStatus.QUEUED, JobStatus.DEFERRED, JobStatus.SCHEDULED):
        job = _fake_job(native)
        with patch("backend.services.forecast_service._get_job", return_value=job):
            view = get_forecast_job("job-pre")
        assert view is not None and view.status == "queued"


def test_stopped_and_canceled_collapse_to_error() -> None:
    """Operator-killed jobs surface as ``error`` so the UI tells the
    user the job won't complete; the audit trail belongs to the
    operator who stopped it."""
    for native in (JobStatus.STOPPED, JobStatus.CANCELED):
        job = _fake_job(native, exc_info=None)
        with patch("backend.services.forecast_service._get_job", return_value=job):
            view = get_forecast_job("job-killed")
        assert view is not None and view.status == "error"
