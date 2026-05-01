"""Grant + revoke + lookup primitives for ``user_entitlements``.

Three pure(-ish) async helpers: ``grant_tier``, ``revoke_by_event``,
and ``tier_for_user``. The Stripe webhook subscriber composes them; an
authenticated request in any other code path can call ``tier_for_user``
to resolve the caller's effective tier without going through the
in-memory tier override.

Idempotency: ``grant_tier`` uses ``INSERT … ON CONFLICT (granted_by_event_id)
DO NOTHING`` so a re-delivered Stripe event collapses to a single row,
even if the in-memory dedupe (``backend.infra.idempotency.record_stripe_event``)
missed (e.g. cross-worker race or post-record crash before grant). The
DB-level unique index is the source of truth.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.entitlement_models import UserEntitlement
from backend.entitlements.features import TIER_RANK, Tier
from backend.infra.logging import get_logger

_log = get_logger(__name__)


async def grant_tier(
    session: AsyncSession,
    *,
    user_id: str,
    tier: Tier,
    granted_by_event_id: str,
) -> bool:
    """Grant ``tier`` to ``user_id`` from ``granted_by_event_id``.

    Returns True when a row was inserted, False on a replay (matching
    ``granted_by_event_id`` already present). Callers that want to fan
    out side effects only on first-grant can branch on the boolean.
    """
    stmt = (
        pg_insert(UserEntitlement)
        .values(
            user_id=user_id,
            tier=tier.value,
            granted_by_event_id=granted_by_event_id,
        )
        .on_conflict_do_nothing(index_elements=["granted_by_event_id"])
        .returning(UserEntitlement.id)
    )
    result = await session.execute(stmt)
    inserted = result.scalar_one_or_none()
    await session.commit()
    if inserted is None:
        _log.info(
            "entitlements.grant_replay_dropped",
            user_id=user_id,
            tier=tier.value,
            event_id=granted_by_event_id,
        )
        return False
    _log.info(
        "entitlements.tier_granted",
        user_id=user_id,
        tier=tier.value,
        event_id=granted_by_event_id,
    )
    return True


async def revoke_by_event(
    session: AsyncSession,
    *,
    user_id: str,
    tier: Tier,
    revoked_by_event_id: str,
) -> bool:
    """Mark the most-recent matching active grant as revoked.

    Two events can refund the same grant — Stripe will re-deliver — so
    we dedupe on ``revoked_by_event_id`` (unique). If no active grant
    exists (already revoked or never existed), returns False without
    raising; the webhook still 200s and the operator inspects the log.
    """
    # Newest active grant matching (user, tier).
    stmt = (
        select(UserEntitlement)
        .where(
            UserEntitlement.user_id == user_id,
            UserEntitlement.tier == tier.value,
            UserEntitlement.revoked_at.is_(None),
        )
        .order_by(desc(UserEntitlement.granted_at))
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        _log.warning(
            "entitlements.revoke_no_active_grant",
            user_id=user_id,
            tier=tier.value,
            event_id=revoked_by_event_id,
        )
        return False

    # Replay guard: if a refund row already references this event, skip.
    replay_stmt = select(UserEntitlement).where(
        UserEntitlement.revoked_by_event_id == revoked_by_event_id
    )
    if (await session.execute(replay_stmt)).scalar_one_or_none() is not None:
        _log.info(
            "entitlements.revoke_replay_dropped",
            user_id=user_id,
            tier=tier.value,
            event_id=revoked_by_event_id,
        )
        return False

    row.revoked_at = datetime.now(UTC)
    row.revoked_by_event_id = revoked_by_event_id
    await session.commit()
    _log.info(
        "entitlements.tier_revoked",
        user_id=user_id,
        tier=tier.value,
        event_id=revoked_by_event_id,
    )
    return True


async def tier_for_user(session: AsyncSession, user_id: str) -> Tier:
    """Effective tier for ``user_id`` — highest active grant, or FREE.

    Returns ``Tier.FREE`` for a user with no rows or only-revoked rows;
    callers don't need to special-case absence.
    """
    stmt = select(UserEntitlement.tier).where(
        UserEntitlement.user_id == user_id,
        UserEntitlement.revoked_at.is_(None),
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return Tier.FREE
    best = Tier.FREE
    best_rank = TIER_RANK[Tier.FREE]
    for raw in rows:
        try:
            tier = Tier(raw)
        except ValueError:
            # Stale row referencing a tier we've since renamed; skip
            # rather than crash the lookup.
            _log.warning("entitlements.unknown_tier_in_row", user_id=user_id, raw=raw)
            continue
        rank = TIER_RANK[tier]
        if rank > best_rank:
            best = tier
            best_rank = rank
    return best


__all__ = ["grant_tier", "revoke_by_event", "tier_for_user"]
