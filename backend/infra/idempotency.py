"""Idempotency for mutating POST endpoints + Stripe webhook dedupe.

Two related primitives, one module:

* `@idempotent(route_key=…, ttl_seconds=…)` decorates a FastAPI handler.
  When the client supplies an `Idempotency-Key` header, the request body
  is hashed and cached against `(key, route)`; a replay returns the
  original cached response, a body mismatch returns HTTP 409. Without
  the header the handler runs as usual — opt-in per-call.

* `record_stripe_event(session, event_id, …)` is the dedupe primitive
  for Stripe webhooks (which key on `event.id` rather than a
  client-supplied header). Returns `True` on the first record and
  `False` on every replay so callers grant entitlements exactly once.

The route key is intentionally explicit (rather than `request.url.path`)
so two routes with the same shape don't collide, and so URL refactors
don't silently invalidate live cache entries.
"""

from __future__ import annotations

import functools
import hashlib
import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, TypeVar, cast

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import backend.database as _db
from backend.db.models import IdempotencyKey, StripeEvent
from backend.infra.logging import get_logger

logger = get_logger(__name__)

DEFAULT_TTL_SECONDS = 60 * 60 * 24  # 24 hours
IDEMPOTENCY_HEADER = "idempotency-key"

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def canonical_request_hash(body: bytes) -> str:
    """Stable sha256 of the raw request body — clients that send
    semantically identical JSON with different whitespace get treated
    as the same request."""
    if not body:
        return hashlib.sha256(b"").hexdigest()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return hashlib.sha256(body).hexdigest()
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


async def _lookup(
    session: AsyncSession, route: str, key: str, now: datetime
) -> IdempotencyKey | None:
    """Return a non-expired cached row, or `None` if novel / expired."""
    result = await session.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.route == route,
            IdempotencyKey.key == key,
            IdempotencyKey.expires_at > now,
        )
    )
    return result.scalar_one_or_none()


async def _save(
    session: AsyncSession,
    *,
    route: str,
    key: str,
    request_hash: str,
    response_status: int,
    response_body: dict[str, Any],
    ttl_seconds: int,
    now: datetime,
) -> None:
    """Insert the response row. Concurrent inserts race-lose harmlessly:
    `ON CONFLICT (key, route) DO NOTHING` keeps the first writer's payload."""
    stmt = (
        pg_insert(IdempotencyKey)
        .values(
            key=key,
            route=route,
            request_hash=request_hash,
            response_status=response_status,
            response_body=response_body,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
        .on_conflict_do_nothing(index_elements=["key", "route"])
    )
    await session.execute(stmt)
    await session.commit()


def idempotent(
    *,
    route_key: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> Callable[[F], F]:
    """Decorate a FastAPI POST handler with idempotency-key replay protection.

    The handler MUST accept a `request: Request` parameter (FastAPI
    populates it). The wrapper inspects `request.headers["idempotency-key"]`:

    * Header absent → handler runs as-is, no caching.
    * Header present, novel → handler runs; response body + status cached
      under `(key, route_key)` for `ttl_seconds`.
    * Header present, replay (hash matches) → cached response returned
      verbatim; handler is NOT invoked.
    * Header present, hash mismatch → HTTP 409.

    The cached response body must be JSON-serialisable. Handlers that
    return a Pydantic model — the FastAPI default — satisfy this for free.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            request: Request | None = kwargs.get("request") or next(
                (a for a in args if isinstance(a, Request)), None
            )
            if request is None:
                # Caller forgot to declare `request: Request` — fail loudly
                # rather than silently disabling idempotency.
                raise RuntimeError(
                    f"@idempotent on {func.__name__} requires a `request: Request` parameter"
                )

            key = request.headers.get(IDEMPOTENCY_HEADER)
            if not key:
                return await func(*args, **kwargs)

            body = await request.body()
            request_hash = canonical_request_hash(body)
            now = datetime.now(UTC)

            async with _db.SessionLocal() as session:
                existing = await _lookup(session, route_key, key, now)
                if existing is not None:
                    if existing.request_hash != request_hash:
                        logger.warning(
                            "idempotency.hash_mismatch",
                            route=route_key,
                            key=key,
                        )
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=(
                                "Idempotency-Key reused with a different request body. "
                                "Pick a fresh key for new requests."
                            ),
                        )
                    logger.info(
                        "idempotency.replay",
                        route=route_key,
                        key=key,
                        cached_status=existing.response_status,
                    )
                    return Response(
                        content=json.dumps(existing.response_body),
                        media_type="application/json",
                        status_code=existing.response_status,
                    )

                result = await func(*args, **kwargs)
                response_body = _serialise_response(result)
                await _save(
                    session,
                    route=route_key,
                    key=key,
                    request_hash=request_hash,
                    response_status=status.HTTP_200_OK,
                    response_body=response_body,
                    ttl_seconds=ttl_seconds,
                    now=now,
                )
                logger.info(
                    "idempotency.stored",
                    route=route_key,
                    key=key,
                    ttl_seconds=ttl_seconds,
                )
            return result

        return cast(F, wrapper)

    return decorator


def _serialise_response(result: Any) -> dict[str, Any]:
    """Coerce a handler return value into a JSON-able dict for caching.

    FastAPI handlers commonly return dict, Pydantic model, or list. We
    only cache dicts; non-dict shapes round-trip through json.dumps so
    a list-returning handler still caches but with a synthetic envelope.
    """
    if hasattr(result, "model_dump"):
        return cast(dict[str, Any], result.model_dump(mode="json"))
    if isinstance(result, dict):
        return result
    return {"_envelope": json.loads(json.dumps(result, default=str))}


async def record_stripe_event(
    session: AsyncSession,
    *,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> bool:
    """Insert a Stripe webhook event; return True if newly recorded.

    Uses `INSERT … ON CONFLICT (event_id) DO NOTHING` so concurrent
    deliveries of the same event collapse to a single ledger row.
    Callers should branch on the return value: only the True branch
    grants entitlements / mutates state."""
    stmt = (
        pg_insert(StripeEvent)
        .values(event_id=event_id, event_type=event_type, payload=payload)
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(StripeEvent.event_id)
    )
    try:
        result = await session.execute(stmt)
    except IntegrityError:
        # Belt-and-braces fallback for backends that don't support ON CONFLICT.
        await session.rollback()
        return False
    inserted = result.scalar_one_or_none()
    await session.commit()
    if inserted is None:
        logger.info("stripe.replay_dropped", event_id=event_id, event_type=event_type)
        return False
    logger.info("stripe.event_recorded", event_id=event_id, event_type=event_type)
    return True


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "IDEMPOTENCY_HEADER",
    "canonical_request_hash",
    "idempotent",
    "record_stripe_event",
]


# `insert` is re-exported for tests that exercise raw inserts; keep the
# import alive for type-checkers in strict mode.
_ = insert
