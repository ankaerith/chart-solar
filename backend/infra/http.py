"""Single front door for outbound HTTP calls.

Every provider that talks to an upstream (NSRDB, PVGIS, Open-Meteo,
Vertex AI, Stripe-read, Enphase, …) goes through `make_get` /
`make_post` here. The decorated callable is bound to one `service` so
the per-service `CircuitBreaker` keys consistently across instances and
processes; the `test_no_raw_httpx_outside_infra` guardrail in
`backend/tests/test_retry.py` enforces this — raw `httpx.Client(...)` or
`httpx.AsyncClient(...)` outside `backend/infra/` fails the suite.

Connection pooling: a single ``httpx.AsyncClient`` per ``service`` key
is cached on the module so repeated calls share TCP + TLS connections
(NSRDB, Vertex, Stripe-read are all TLS endpoints — fresh handshakes
on every call cost 50–200 ms each). The cache lives for the lifetime
of the process; ``aclose_all_clients()`` is invoked from FastAPI's
shutdown handler and from the worker bootstrap so the pool drains
cleanly. Tests that need to reset the cache call
``aclose_all_clients()`` between cases.

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

#: One AsyncClient per ``service`` key, lazily created. The lock guards
#: the build-on-first-use race so two concurrent first-callers don't
#: each build their own client + leak the loser.
_CLIENTS: dict[str, httpx.AsyncClient] = {}


def _get_client(service: str, *, timeout: float) -> httpx.AsyncClient:
    """Return the shared AsyncClient for ``service``, building once.

    Timeout is a property of the client at construction time. Per-call
    timeout overrides happen at the request layer (``client.get(...,
    timeout=X)``); the ``timeout`` argument here only sets the default
    used when the caller doesn't override.
    """
    client = _CLIENTS.get(service)
    if client is None:
        client = httpx.AsyncClient(timeout=timeout)
        _CLIENTS[service] = client
    return client


async def aclose_all_clients() -> None:
    """Drain every cached AsyncClient. Wire into FastAPI lifespan + worker
    shutdown so process exit doesn't leak open sockets.

    Idempotent: closing a client that was already closed is a no-op.
    """
    for client in list(_CLIENTS.values()):
        await client.aclose()
    _CLIENTS.clear()


def make_get(*, service: str, config: RetryConfig | None = None) -> GetFn:
    """Build a retry-wrapped HTTP GET bound to `service`.

    Calling this multiple times with the same service is safe — the
    breaker registry in `retry.py` is keyed on `service`, and the
    AsyncClient cache is keyed on `service` too, so all callers share
    both connection state and the breaker.
    """

    @retry(service=service, config=config, retry_on=(httpx.HTTPError,))
    async def get(
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> httpx.Response:
        client = _get_client(service, timeout=timeout)
        response = await client.get(url, params=params, headers=headers, timeout=timeout)
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
        client = _get_client(service, timeout=timeout)
        response = await client.post(
            url, json=json, params=params, headers=headers, timeout=timeout
        )
        response.raise_for_status()
        return response

    return post


__all__ = [
    "DEFAULT_TIMEOUT_S",
    "GetFn",
    "PostFn",
    "aclose_all_clients",
    "make_get",
    "make_post",
]
