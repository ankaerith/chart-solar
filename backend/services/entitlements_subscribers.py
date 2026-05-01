"""Event-bus subscribers that translate payment events into ledger writes.

Two async handlers, one each for :class:`PaymentSucceeded` and
:class:`PaymentRefunded`. They open a fresh DB session per event so a
slow handler doesn't hold a connection borrowed from a request context.

Registration runs through :func:`register_subscribers` so a worker
that runs *only* the entitlements layer can call it from its own
bootstrap; tests reset state via :func:`backend.infra.eventbus.clear_subscribers`
between cases and re-register as needed.
"""

from __future__ import annotations

import backend.database as _db
from backend.domain.events import PaymentRefunded, PaymentSucceeded
from backend.entitlements.features import try_parse_tier
from backend.infra.eventbus import subscribe
from backend.infra.logging import get_logger
from backend.services.entitlements_grants import grant_tier, revoke_by_event

_log = get_logger(__name__)


def register_subscribers() -> None:
    """Register the payment handlers on the in-process event bus."""
    subscribe(PaymentSucceeded)(_on_payment_succeeded)
    subscribe(PaymentRefunded)(_on_payment_refunded)


async def _on_payment_succeeded(event: PaymentSucceeded) -> None:
    tier = try_parse_tier(event.tier)
    if tier is None:
        _log.warning(
            "entitlements.payment_unknown_tier",
            user_id=event.user_id,
            tier=event.tier,
            event_id=event.stripe_event_id,
        )
        return
    async with _db.SessionLocal() as session:
        await grant_tier(
            session,
            user_id=event.user_id,
            tier=tier,
            granted_by_event_id=event.stripe_event_id,
        )


async def _on_payment_refunded(event: PaymentRefunded) -> None:
    tier = try_parse_tier(event.tier)
    if tier is None:
        _log.warning(
            "entitlements.refund_unknown_tier",
            user_id=event.user_id,
            tier=event.tier,
            event_id=event.stripe_event_id,
        )
        return
    async with _db.SessionLocal() as session:
        await revoke_by_event(
            session,
            user_id=event.user_id,
            tier=tier,
            revoked_by_event_id=event.stripe_event_id,
        )


__all__ = ["register_subscribers"]
