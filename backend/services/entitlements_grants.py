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

from sqlalchemy import case, desc, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.entitlement_models import UserEntitlement
from backend.entitlements.features import TIER_RANK, Tier
from backend.infra.logging import get_logger
from backend.infra.util import utc_now

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

    The unique constraint on ``revoked_by_event_id`` is the replay
    guard — a re-delivered refund event raises ``IntegrityError`` on
    commit, which we catch and translate to ``False``. No active grant
    matching (user, tier) also returns ``False``; the webhook still
    200s and the operator inspects the log.
    """
    candidate_id = (
        select(UserEntitlement.id)
        .where(
            UserEntitlement.user_id == user_id,
            UserEntitlement.tier == tier.value,
            UserEntitlement.revoked_at.is_(None),
        )
        .order_by(desc(UserEntitlement.granted_at))
        .limit(1)
        .scalar_subquery()
    )
    stmt = (
        update(UserEntitlement)
        .where(UserEntitlement.id == candidate_id)
        .values(
            revoked_at=utc_now(),
            revoked_by_event_id=revoked_by_event_id,
        )
        .returning(UserEntitlement.id)
    )
    try:
        result = await session.execute(stmt)
        await session.commit()
    except IntegrityError:
        # Unique on revoked_by_event_id tripped — replay.
        await session.rollback()
        _log.info(
            "entitlements.revoke_replay_dropped",
            user_id=user_id,
            tier=tier.value,
            event_id=revoked_by_event_id,
        )
        return False

    if result.scalar_one_or_none() is None:
        _log.warning(
            "entitlements.revoke_no_active_grant",
            user_id=user_id,
            tier=tier.value,
            event_id=revoked_by_event_id,
        )
        return False
    _log.info(
        "entitlements.tier_revoked",
        user_id=user_id,
        tier=tier.value,
        event_id=revoked_by_event_id,
    )
    return True


_TIER_RANK_CASE = case(
    {member.value: TIER_RANK[member] for member in TIER_RANK},
    value=UserEntitlement.tier,
    else_=-1,
)


async def tier_for_user(session: AsyncSession, user_id: str) -> Tier:
    """Effective tier for ``user_id`` — highest active grant, or FREE.

    Returns ``Tier.FREE`` for a user with no rows or only-revoked rows.
    Ranking happens in SQL; the ``else_=-1`` clause sorts unrecognised
    tier strings (e.g. a column value renamed since this row was
    written) below every known tier so a stale row can't win.
    """
    raw = await session.scalar(
        select(UserEntitlement.tier)
        .where(
            UserEntitlement.user_id == user_id,
            UserEntitlement.revoked_at.is_(None),
        )
        .order_by(_TIER_RANK_CASE.desc())
        .limit(1)
    )
    if raw is None:
        return Tier.FREE
    try:
        return Tier(raw)
    except ValueError:
        _log.warning("entitlements.unknown_tier_in_row", user_id=user_id, raw=raw)
        return Tier.FREE


__all__ = ["grant_tier", "revoke_by_event", "tier_for_user"]
