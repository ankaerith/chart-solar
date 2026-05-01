"""Entitlement ledger backing the Stripe webhook subscriber.

A row per `(user, tier, granting Stripe event)`. The ``granted_by_event_id``
column is unique so the subscriber's idempotency comes from the
database, not just the in-memory event-bus dedupe — a worker that
restarts mid-handler can re-deliver the event safely. A refund flips
``revoked_at`` (and records the refund's Stripe event ID) rather than
deleting the row, so the audit trail of "who was on what tier when"
stays intact.

Active tier resolution lives in ``backend.services.entitlements_grants``:
a user's effective tier is the highest-rank non-revoked entitlement they
hold; absent any rows the user is on ``Tier.FREE``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class UserEntitlement(Base):
    """One grant of a tier to a user, sourced from a single Stripe event."""

    __tablename__ = "user_entitlements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(64), nullable=False)
    # Unique so a Stripe event re-delivery can't grant twice; the
    # webhook-dedupe ledger (``stripe_events``) catches most replays
    # but this is the belt to the suspenders for a worker that crashes
    # between dispatch and grant.
    granted_by_event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    revoked_by_event_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
