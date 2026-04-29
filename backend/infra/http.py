"""Single front door for outbound HTTP calls.

Every provider that talks to an upstream (NSRDB, PVGIS, Open-Meteo,
Vertex AI, Stripe-read, Enphase, …) goes through `make_get` /
`make_post` here. The decorated callable is bound to one `service` so
the per-service `CircuitBreaker` keys consistently across instances and
processes; the `test_no_raw_httpx_outside_infra` guardrail in
`backend/tests/test_retry.py` enforces this — raw `httpx.Client(...)` or
`httpx.AsyncClient(...)` outside `backend/infra/` fails the suite.

Usage:

    from backend.infra.http import make_get

    class NsrdbProvider:
        def __init__(self) -> None:
            self._get = make_get(service="nsrdb")

        async def fetch(self) -> httpx.Response:
            return await self._get(NSRDB_URL, params={...})
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from backend.infra.retry import RetryConfig, retry

DEFAULT_TIMEOUT_S = 30.0

GetFn = Callable[..., Awaitable[httpx.Response]]
PostFn = Callable[..., Awaitable[httpx.Response]]


def make_get(*, service: str, config: RetryConfig | None = None) -> GetFn:
    """Build a retry-wrapped HTTP GET bound to `service`.

    Calling this multiple times with the same service is safe — the
    breaker registry in `retry.py` is keyed on `service`, so all callers
    share state. Each returned callable is otherwise independent.
    """

    @retry(service=service, config=config, retry_on=(httpx.HTTPError,))
    async def get(
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response

    return get


def make_post(*, service: str, config: RetryConfig | None = None) -> PostFn:
    """Build a retry-wrapped HTTP POST bound to `service`."""

    @retry(service=service, config=config, retry_on=(httpx.HTTPError,))
    async def post(
        url: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=json, params=params, headers=headers)
            response.raise_for_status()
            return response

    return post


__all__ = ["DEFAULT_TIMEOUT_S", "GetFn", "PostFn", "make_get", "make_post"]
