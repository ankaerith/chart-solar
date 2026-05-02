"""Redis-backed sliding-window rate limiter.

One primitive (``check_rate_limit``) and a FastAPI ``Depends`` factory
(``rate_limit_dependency``) that callers compose at route-registration
time. The implementation is the standard fixed-window counter:
``INCR`` the bucket key, ``EXPIRE`` it to the window size on the first
hit, refuse once the count exceeds ``limit``.

Why fixed-window over a token bucket: this is good enough for "stop
the obvious abuser" (login email spam, anonymous queue flooding) and
keeps the data path to one round-trip with no Lua. Bursts at window
edges are acceptable for these endpoints — the threat model is sustained
abuse, not microsecond-precision throttling.

Redis is the only state, so multiple API workers share counters
without coordination. A Redis outage degrades to "allow" rather than
"deny everything"; the rest of the stack treats Redis as a soft
dependency for the same reason (queue.py + idempotency.py both have
explicit "if Redis is down" guards).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import lru_cache

import redis.asyncio as redis_async
from fastapi import HTTPException, Request, status

from backend.config import settings
from backend.infra.logging import get_logger

_log = get_logger(__name__)

#: Default ceiling on per-IP login attempts inside the window. Tuned
#: to allow legitimate retry on a typo'd email + a re-issue when the
#: first link expired, while flagging password-spray-equivalent volume.
LOGIN_PER_IP_LIMIT = 20
LOGIN_PER_IP_WINDOW_SECONDS = 60 * 60  # 1 hour

#: Default ceiling on per-email magic-link issuance. The user only
#: needs one valid link in the 15-minute TTL window; allowing five
#: re-issues per hour covers "click expired link, request another"
#: without giving the spammer free transactional email.
LOGIN_PER_EMAIL_LIMIT = 5
LOGIN_PER_EMAIL_WINDOW_SECONDS = 60 * 60  # 1 hour


@lru_cache(maxsize=1)
def get_rate_limit_redis() -> redis_async.Redis:
    """Async Redis client dedicated to the rate-limit bucket reads/writes.

    A separate cached client (vs. the sync queue client in
    ``workers.queue.get_redis``) so middleware code paths don't trip
    asyncio.to_thread on every request.
    """
    return redis_async.Redis.from_url(settings.redis_url)


async def check_rate_limit(
    redis_client: redis_async.Redis,
    *,
    key: str,
    limit: int,
    window_seconds: int,
) -> bool:
    """Atomically increment the bucket; return True iff under ``limit``.

    On Redis failure we log and return True (fail-open) — refusing to
    accept any login because Redis is sick is a worse outcome than
    relaxing the throttle for the duration of the outage.
    """
    try:
        count: int = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, window_seconds)
    except Exception as exc:  # noqa: BLE001 — fail-open on Redis outage
        _log.warning("rate_limit.redis_unavailable", key=key, error=repr(exc))
        return True
    return bool(count <= limit)


def _client_ip(request: Request) -> str:
    """Best-effort caller IP for rate-limit bucketing.

    Trusts ``X-Forwarded-For`` only if the deployment sits behind a
    reverse proxy (operator concern); falls back to the direct peer
    address. Picking a stable per-caller token is the contract — the
    proxy fronting prod must scrub any client-supplied XFF before
    overwriting it, otherwise a hostile client can cycle through
    fabricated IPs to dodge the bucket.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First entry is the originating client per the standard.
        return forwarded.split(",", 1)[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def rate_limit_dependency(
    *,
    bucket: str,
    limit: int,
    window_seconds: int,
    key_fn: Callable[[Request], Awaitable[str] | str],
) -> Callable[[Request], Awaitable[None]]:
    """Build a FastAPI ``Depends`` that 429s when the bucket overflows.

    ``bucket`` namespaces the Redis key so two route-level limiters
    don't collide. ``key_fn`` extracts the per-caller identifier
    (typically IP, email, or a tuple thereof). It can be sync or async
    so callers can pull a Pydantic-validated body field after the
    request body is parsed; for IP-only limiters the sync path is
    enough.
    """

    async def _check(request: Request) -> None:
        raw_key = key_fn(request)
        key_value = await raw_key if hasattr(raw_key, "__await__") else raw_key
        redis_key = f"rl:{bucket}:{key_value}"
        client = get_rate_limit_redis()
        allowed = await check_rate_limit(
            client,
            key=redis_key,
            limit=limit,
            window_seconds=window_seconds,
        )
        if not allowed:
            _log.warning(
                "rate_limit.exceeded",
                bucket=bucket,
                key=key_value,
                limit=limit,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="rate limit exceeded; try again later",
            )

    return _check


def per_ip_dependency(
    *, bucket: str, limit: int, window_seconds: int
) -> Callable[[Request], Awaitable[None]]:
    """Convenience wrapper for the IP-only bucket — the most common case."""
    return rate_limit_dependency(
        bucket=bucket,
        limit=limit,
        window_seconds=window_seconds,
        key_fn=_client_ip,
    )


__all__ = [
    "LOGIN_PER_EMAIL_LIMIT",
    "LOGIN_PER_EMAIL_WINDOW_SECONDS",
    "LOGIN_PER_IP_LIMIT",
    "LOGIN_PER_IP_WINDOW_SECONDS",
    "check_rate_limit",
    "get_rate_limit_redis",
    "per_ip_dependency",
    "rate_limit_dependency",
]
