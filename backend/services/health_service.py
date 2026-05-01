"""Health-check probes — db + queue.

The /api/health route assembles the response shape; the actual probes
live here so the api layer never imports ``backend.workers``. Each
probe swallows exceptions and returns a bool — health checks must
not raise.
"""

from __future__ import annotations

import asyncio

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


async def queue_ok() -> bool:
    """Redis ``PING`` against the queue's connection.

    redis-py's PING is synchronous, so we offload it to a thread —
    a slow Redis (or a TCP-level hang) would otherwise stall the event
    loop, which would in turn block every other in-flight request.
    """

    def _ping() -> bool:
        try:
            get_redis().ping()
        except Exception:
            return False
        return True

    return await asyncio.to_thread(_ping)


__all__ = ["database_ok", "queue_ok"]
