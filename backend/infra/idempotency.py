"""Idempotency for mutating POST endpoints + Stripe webhook dedupe.

Three primitives, one module:

* ``canonical_request_hash(body)`` — stable SHA-256 of a request body.
* ``claim_idempotency_slot(...)`` — atomic ``(route, key)`` claim that
  callers wrap around any side-effectful work (queue enqueue, charge
  card, etc.). The first writer wins; concurrent identical-key requests
  collapse to the winner's cached response.
* ``record_stripe_event(...)`` — dedupe primitive for Stripe webhooks
  keyed on ``event.id``.

The route key is intentionally explicit (rather than ``request.url.path``)
so two routes with the same shape don't collide, and so URL refactors
don't silently invalidate live cache entries.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import IdempotencyKey, StripeEvent
from backend.infra.logging import get_logger
from backend.infra.util import sha256_hex, utc_now

logger = get_logger(__name__)

DEFAULT_TTL_SECONDS = 60 * 60 * 24  # 24 hours
IDEMPOTENCY_HEADER = "idempotency-key"


def canonical_request_hash(body: bytes) -> str:
    """Stable sha256 of the raw request body.

    Whitespace and key ordering collapse to the same hash (``json.loads``
    + sorted-key ``json.dumps``). Float precision normalises through
    Python's float repr (``5.50`` and ``5.5`` collide; both load as
    ``5.5``). Integer-vs-float literals do **not** collide: ``1`` and
    ``1.0`` round-trip back to different JSON literals (``1`` vs ``1.0``)
    and therefore hash differently — the cost is one duplicate enqueue
    when a client toggles the literal style for the same numeric value;
    there is no correctness risk because the worker reads typed
    Pydantic inputs either way.
    """
    if not body:
        return sha256_hex(b"")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return sha256_hex(body)
    canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_hex(canonical)


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


def _claim_insert_stmt(
    *,
    route: str,
    key: str,
    request_hash: str,
    response_status: int,
    response_body: dict[str, Any],
    expires_at: datetime,
    returning: bool,
) -> Any:
    """Shared ``INSERT … ON CONFLICT (key, route) DO NOTHING`` builder."""
    stmt = (
        pg_insert(IdempotencyKey)
        .values(
            key=key,
            route=route,
            request_hash=request_hash,
            response_status=response_status,
            response_body=response_body,
            expires_at=expires_at,
        )
        .on_conflict_do_nothing(index_elements=["key", "route"])
    )
    return stmt.returning(IdempotencyKey.key) if returning else stmt


async def lookup_idempotency_response(
    session: AsyncSession,
    *,
    route: str,
    key: str,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Return the cached response body for ``(route, key)`` if non-expired.

    Public facade over ``_lookup`` for callers that derive the
    idempotency key from the request body rather than a header — they
    don't need direct ORM access, just the cached response bytes.
    """
    row = await _lookup(session, route, key, now or utc_now())
    if row is None:
        return None
    return dict(row.response_body)


async def claim_idempotency_slot(
    session: AsyncSession,
    *,
    route: str,
    key: str,
    request_hash: str,
    response_body: dict[str, Any],
    response_status: int = 200,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    now: datetime | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Atomically claim ``(route, key)`` with ``response_body``.

    Returns ``(won, body)``: ``won`` is True iff this call inserted the
    row (the caller should now run its side effect — enqueue a job,
    charge a card — and return ``body``); ``won`` is False on a race
    loss, in which case ``body`` is the prior writer's cached response.
    """
    when = now or utc_now()
    result = await session.execute(
        _claim_insert_stmt(
            route=route,
            key=key,
            request_hash=request_hash,
            response_status=response_status,
            response_body=response_body,
            expires_at=when + timedelta(seconds=ttl_seconds),
            returning=True,
        )
    )
    won = result.scalar_one_or_none() is not None
    await session.commit()
    if won:
        return True, response_body
    existing = await lookup_idempotency_response(session, route=route, key=key, now=when)
    if existing is None:
        # Pathological: a row was inserted then expired between our
        # INSERT and our follow-up SELECT. We treat this as race-WON so
        # the caller runs its side effect — returning the would-be
        # response without enqueueing would hand the client a job_id
        # for a job that never ran.
        return True, response_body
    return False, existing


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
    "claim_idempotency_slot",
    "lookup_idempotency_response",
    "record_stripe_event",
]
