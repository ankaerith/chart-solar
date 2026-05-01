"""POST /api/stripe/webhook — receives + dedupes + dispatches.

Flow:

1. Read the raw body (signature verification needs the unmodified bytes).
2. Verify the ``Stripe-Signature`` header against ``STRIPE_WEBHOOK_SECRET``;
   on failure return HTTP 400 — Stripe re-delivers and retries until
   the secret matches or the event ages out, so a 4xx here is the right
   loud signal for a misconfigured deploy.
3. Insert into ``stripe_events`` (the dedupe ledger). On a replay, return
   ``{status: "replay"}`` and don't dispatch — the bus subscribers ran on
   the first delivery.
4. Translate to a domain event (``PaymentSucceeded`` / ``PaymentRefunded``)
   and ``await dispatch_async`` so the entitlement subscriber completes
   before the response lands back at Stripe.

Per ``docs/ENGINEERING.md`` § Operational expectations: every webhook
is signed, idempotent, and logged with the upstream event id.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

import backend.database as _db
from backend.infra.eventbus import dispatch_async
from backend.infra.idempotency import record_stripe_event
from backend.infra.logging import get_logger
from backend.services.stripe_webhook_router import (
    StripeSignatureError,
    construct_event,
    route_event,
)

router = APIRouter()
_log = get_logger(__name__)


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="Stripe-Signature"),
) -> dict[str, Any]:
    body = await request.body()

    try:
        event = construct_event(payload=body, signature_header=stripe_signature)
    except StripeSignatureError as exc:
        _log.warning("stripe.signature_invalid", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid Stripe signature",
        ) from exc

    event_id = event.get("id")
    event_type = event.get("type")
    if not isinstance(event_id, str) or not isinstance(event_type, str):
        # Stripe payloads always carry both; a missing field is a
        # signature-passing payload that shouldn't have made it through.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="malformed Stripe event",
        )

    async with _db.SessionLocal() as session:
        recorded = await record_stripe_event(
            session,
            event_id=event_id,
            event_type=event_type,
            payload=event,
        )

    if not recorded:
        _log.info("stripe.replay_acknowledged", event_id=event_id, event_type=event_type)
        return {"status": "replay", "event_id": event_id}

    domain_event = route_event(event)
    if domain_event is None:
        # Either an event-type we don't act on, or a handled type
        # missing required metadata. We've already recorded the event;
        # nothing else to do.
        return {"status": "ignored", "event_id": event_id, "event_type": event_type}

    await dispatch_async(domain_event)
    _log.info(
        "stripe.event_dispatched",
        event_id=event_id,
        event_type=event_type,
        domain_event=type(domain_event).__name__,
    )
    return {"status": "ok", "event_id": event_id}
