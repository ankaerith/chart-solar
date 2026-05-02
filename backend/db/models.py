"""ORM tables backing the idempotency utility.

`idempotency_keys` caches request → response for any mutating POST endpoint
that opts in via :func:`backend.infra.idempotency.claim_idempotency_slot`.
`stripe_events` is the companion dedupe ledger for Stripe webhooks (which
key on `event.id` rather than a client-supplied `Idempotency-Key`).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, PrimaryKeyConstraint, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class IdempotencyKey(Base):
    """Request → response cache, scoped per route.

    The composite (`key`, `route`) primary key namespaces idempotency keys
    per endpoint so two routes can safely accept the same client-supplied key.
    `request_hash` lets us reject mismatched bodies (HTTP 409) while still
    serving replays of the same request.
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (PrimaryKeyConstraint("key", "route", name="pk_idempotency_keys"),)

    key: Mapped[str] = mapped_column(String(255), nullable=False)
    route: Mapped[str] = mapped_column(String(255), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    response_body: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StripeEvent(Base):
    """Stripe webhook dedupe ledger.

    A single row per Stripe `event.id`. `INSERT … ON CONFLICT DO NOTHING`
    is the dedupe primitive: only the first writer wins, all replays no-op
    so entitlement grants happen exactly once.
    """

    __tablename__ = "stripe_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
