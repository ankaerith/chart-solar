"""Health-check probes — db + queue.

The /api/health route assembles the response shape; the actual probe
of "is the queue's Redis reachable?" lives here so the api layer never
imports ``backend.workers``. Each probe swallows exceptions and
returns a bool — health checks must not raise.
"""

from __future__ import annotations

from sqlalchemy import text

from backend.database import SessionLocal
from backend.workers.queue import get_redis


async def database_ok() -> bool:
    """Cheap ``SELECT 1`` against the configured Postgres engine.

    Async because the rest of the app is async; a sync hop here would
    block the event loop on a slow connection check. Any exception
    (timeout, auth, schema not present) is treated as a degraded probe.
    """
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


def queue_ok() -> bool:
    """Synchronous Redis ``PING`` against the queue's connection.

    redis-py's PING is sync and fast; the route awaits the function as
    a coroutine but the call itself doesn't need an event loop. Routes
    treat ``False`` as a degraded probe; the operator reads structured
    logs to identify the underlying connection failure.
    """
    try:
        get_redis().ping()
    except Exception:
        return False
    return True


__all__ = ["database_ok", "queue_ok"]
