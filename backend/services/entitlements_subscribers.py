"""Event-bus subscribers that translate payment events into ledger writes.

Two async handlers, one each for :class:`PaymentSucceeded` and
:class:`PaymentRefunded`. They open a fresh DB session per event so a
slow handler doesn't hold a connection borrowed from a request context.

The handlers are registered via :func:`register_subscribers` rather
than module-import side effects so:

* tests can opt in (``register_subscribers()``) and opt out
  (``clear_subscribers()`` is the existing teardown);
* a worker process that runs *only* the entitlements layer can call
  ``register_subscribers()`` from its own bootstrap without the API
  process having to import this module at all.
"""

from __future__ import annotations

import backend.database as _db
from backend.domain.events import PaymentRefunded, PaymentSucceeded
from backend.entitlements.features import Tier
from backend.infra.eventbus import subscribe
from backend.infra.logging import get_logger
from backend.services.entitlements_grants import grant_tier, revoke_by_event

_log = get_logger(__name__)

_REGISTERED = False


def register_subscribers() -> None:
    """Idempotent: register the payment handlers once per process."""
    global _REGISTERED
    if _REGISTERED:
        return

    @subscribe(PaymentSucceeded)
    async def _on_payment_succeeded(event: PaymentSucceeded) -> None:
        tier = _coerce_tier(event.tier, kind="payment", event=event)
        if tier is None:
            return
        async with _db.SessionLocal() as session:
            await grant_tier(
                session,
                user_id=event.user_id,
                tier=tier,
                granted_by_event_id=event.stripe_event_id,
            )

    @subscribe(PaymentRefunded)
    async def _on_payment_refunded(event: PaymentRefunded) -> None:
        tier = _coerce_tier(event.tier, kind="refund", event=event)
        if tier is None:
            return
        async with _db.SessionLocal() as session:
            await revoke_by_event(
                session,
                user_id=event.user_id,
                tier=tier,
                revoked_by_event_id=event.stripe_event_id,
            )

    _REGISTERED = True


def reset_for_tests() -> None:
    """Allow tests to re-register after ``clear_subscribers``."""
    global _REGISTERED
    _REGISTERED = False


def _coerce_tier(raw: str, *, kind: str, event: PaymentSucceeded | PaymentRefunded) -> Tier | None:
    try:
        return Tier(raw)
    except ValueError:
        _log.warning(
            f"entitlements.{kind}_unknown_tier",
            user_id=event.user_id,
            tier=raw,
            event_id=event.stripe_event_id,
        )
        return None


__all__ = ["register_subscribers", "reset_for_tests"]
