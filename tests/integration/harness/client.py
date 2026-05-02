"""Async HTTP client for the forecast API.

Submits a `ForecastInputs` body to ``POST /api/forecast``, then polls
``GET /api/forecast/{job_id}`` until the worker reports completion.
The forecast endpoint is queue-backed (Redis + RQ), so a successful
POST returns immediately with ``status: "queued"``; the actual engine
run happens out-of-band.

Status names match what ``backend.workers.forecast_worker`` writes
back to the job record. Treat any unknown status as still-running so
a backend status-name change doesn't quietly cause the harness to
report success on an in-flight job.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

#: Statuses that mean "done, result is final and ready to compare."
TERMINAL_OK_STATUSES: frozenset[str] = frozenset({"succeeded", "finished", "done"})

#: Statuses that mean "done, the engine raised — no result to compare."
TERMINAL_FAIL_STATUSES: frozenset[str] = frozenset({"failed", "errored"})


class ForecastTimeoutError(Exception):
    """Raised when polling exceeds the configured wall-clock budget."""


class ForecastFailedError(Exception):
    """Raised when the worker reports a terminal failure status."""


async def submit(client: httpx.AsyncClient, base_url: str, inputs: dict[str, Any]) -> str:
    """POST inputs to the forecast endpoint; return the assigned job_id.

    A 4xx / 5xx surfaces via ``raise_for_status`` — the case is
    invalid (422 = body shape) or the server is broken (5xx). Either
    way, the harness should fail loudly rather than treat the case
    as a pending job.
    """
    response = await client.post(f"{base_url}/api/forecast", json=inputs)
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return str(body["job_id"])


async def poll(
    client: httpx.AsyncClient,
    base_url: str,
    job_id: str,
    *,
    timeout_s: float = 120.0,
    interval_s: float = 1.0,
) -> dict[str, Any]:
    """Poll until the job reaches a terminal status, or time out.

    Returns the full ``GET /api/forecast/{job_id}`` body — caller
    extracts ``["result"]`` and walks the artifact tree from there.
    """
    elapsed = 0.0
    while elapsed < timeout_s:
        response = await client.get(f"{base_url}/api/forecast/{job_id}")
        response.raise_for_status()
        body: dict[str, Any] = response.json()
        status = body.get("status", "")
        if status in TERMINAL_OK_STATUSES:
            return body
        if status in TERMINAL_FAIL_STATUSES:
            raise ForecastFailedError(
                f"job {job_id} failed: {body.get('error', '<no error body>')}"
            )
        await asyncio.sleep(interval_s)
        elapsed += interval_s
    raise ForecastTimeoutError(f"job {job_id} still running after {timeout_s:.1f}s")


async def run_case(
    client: httpx.AsyncClient,
    base_url: str,
    inputs: dict[str, Any],
    *,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """Submit + poll, returning the final job body when complete."""
    job_id = await submit(client, base_url, inputs)
    return await poll(client, base_url, job_id, timeout_s=timeout_s)
