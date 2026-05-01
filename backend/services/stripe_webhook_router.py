"""Map Stripe webhook events onto domain payment events.

Pure-ish: the parse + signature-verify is deterministic and has no DB
or HTTP side effects. The dispatcher upstairs (``backend/api/stripe_webhook.py``)
takes the parsed envelope, dedupes via ``record_stripe_event``, and
fires the domain event onto the bus where the entitlements subscriber
picks it up.

Mapping policy v1 — minimal but defensible:

* ``checkout.session.completed`` → :class:`PaymentSucceeded`. The user
  id comes from ``session.client_reference_id`` (set by the checkout
  flow) or ``session.metadata.user_id`` as a fallback. The tier comes
  from ``session.metadata.tier`` — the checkout flow stamps this when
  it creates the session (see chart-solar-5hq / 79i).
* ``invoice.payment_succeeded`` → :class:`PaymentSucceeded`. Same
  metadata contract; the subscription's metadata is propagated onto
  the invoice when the checkout flow creates the subscription.
* ``charge.refunded`` → :class:`PaymentRefunded`. Reads
  ``charge.metadata.user_id`` + ``charge.metadata.tier`` (the checkout
  flow stamps these on the underlying PaymentIntent so the values
  surface on the charge).
* anything else → ``None`` (the webhook still 200s; we just don't
  emit an event).

Anything not understood is logged + ignored. We never raise to Stripe;
their retry policy is aggressive and a 5xx on a benign event-type
floods the dead-letter bucket.
"""

from __future__ import annotations

from typing import Any

from backend.config import require, settings
from backend.domain.events import PaymentRefunded, PaymentSucceeded
from backend.entitlements.features import Tier, try_parse_tier
from backend.infra.logging import get_logger

_log = get_logger(__name__)


# Stripe event types we care about. Any other event type is silently
# acknowledged.
HANDLED_EVENT_TYPES = frozenset(
    {
        "checkout.session.completed",
        "invoice.payment_succeeded",
        "charge.refunded",
    }
)


class StripeSignatureError(ValueError):
    """Raised when Stripe webhook signature verification fails."""


def construct_event(
    *, payload: bytes, signature_header: str, secret: str | None = None
) -> dict[str, Any]:
    """Verify the Stripe webhook signature and return the parsed event.

    Wraps ``stripe.Webhook.construct_event`` so the rest of the
    pipeline doesn't have to import ``stripe`` directly. Verification
    failures bubble up as :class:`StripeSignatureError` (a ``ValueError``)
    so the route layer can return 400.
    """
    import stripe  # noqa: PLC0415

    secret = secret or require(settings.stripe_webhook_secret, "STRIPE_WEBHOOK_SECRET")
    try:
        event = stripe.Webhook.construct_event(  # type: ignore[no-untyped-call]
            payload, signature_header, secret
        )
    except stripe.SignatureVerificationError as exc:
        raise StripeSignatureError("invalid Stripe signature") from exc
    # ``stripe.Event`` is dict-like but not a dict; coerce so the rest
    # of the pipeline only sees a plain JSON-shaped mapping.
    if hasattr(event, "to_dict"):
        return dict(event.to_dict())
    return dict(event)


def route_event(event: dict[str, Any]) -> PaymentSucceeded | PaymentRefunded | None:
    """Translate a parsed Stripe event into our domain event, or None.

    Returns ``None`` for unhandled event types or for handled ones that
    are missing required metadata — the caller logs and 200s.
    """
    event_type = event.get("type")
    event_id = event.get("id")
    if not isinstance(event_type, str) or not isinstance(event_id, str):
        _log.warning("stripe.malformed_event", payload_preview=str(event)[:256])
        return None

    if event_type not in HANDLED_EVENT_TYPES:
        _log.info("stripe.event_ignored", event_type=event_type, event_id=event_id)
        return None

    obj = ((event.get("data") or {}).get("object")) or {}
    user_id, tier = _extract_user_and_tier(event_type, obj)
    if user_id is None or tier is None:
        _log.warning(
            "stripe.event_missing_metadata",
            event_type=event_type,
            event_id=event_id,
        )
        return None

    if event_type == "charge.refunded":
        return PaymentRefunded(
            user_id=user_id,
            tier=tier.value,
            stripe_event_id=event_id,
        )
    return PaymentSucceeded(
        user_id=user_id,
        tier=tier.value,
        stripe_event_id=event_id,
    )


def _extract_user_and_tier(event_type: str, obj: dict[str, Any]) -> tuple[str | None, Tier | None]:
    """Pull user_id + tier from the canonical metadata locations.

    Policy is event-type specific because Stripe's metadata is attached
    to different sub-objects depending on the event:

    * ``checkout.session.completed`` — user comes from
      ``client_reference_id`` (the Stripe-recommended channel) and falls
      back to ``metadata.user_id``; tier is always ``metadata.tier``.
    * ``invoice.payment_succeeded`` — both fields live on the
      invoice's ``metadata`` (the checkout flow propagates them onto
      the subscription, which copies onto the invoice).
    * ``charge.refunded`` — the original PaymentIntent is the source
      of truth; ``metadata.user_id`` + ``metadata.tier`` were stamped
      there at checkout time and Stripe surfaces them on the charge.
    """
    metadata = (obj.get("metadata") or {}) if isinstance(obj.get("metadata"), dict) else {}

    raw_tier = metadata.get("tier")
    tier = try_parse_tier(raw_tier) if isinstance(raw_tier, str) else None
    if tier is None and isinstance(raw_tier, str):
        _log.warning("stripe.unknown_tier", raw=raw_tier)

    if event_type == "checkout.session.completed":
        user_id = obj.get("client_reference_id") or metadata.get("user_id")
    else:
        user_id = metadata.get("user_id")

    return (user_id if isinstance(user_id, str) and user_id else None, tier)


__all__ = [
    "HANDLED_EVENT_TYPES",
    "StripeSignatureError",
    "construct_event",
    "route_event",
]
