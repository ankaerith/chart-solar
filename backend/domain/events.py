"""Typed event payloads dispatched through ``backend.infra.eventbus``.

Events are frozen dataclasses — they're addressed by class identity
rather than a string key, so the dispatcher matches subscribers via
the event's runtime type and a typo at the publish site fails at
import time instead of silently going un-subscribed.

Each event carries an ``event_id`` so subscribers can dedupe replays
(the entitlements grant is the canonical example: a Stripe webhook
might fire twice, but we only credit the user once). The ``occurred_at``
field is the publisher-side wall-clock — useful for telemetry but not
for ordering decisions, which the in-process bus doesn't guarantee.

Field types are tightened where the producer can validate once at the
boundary — see ``PaymentSucceeded.tier`` / ``PaymentRefunded.tier``
typed as :class:`Tier` so subscribers don't each re-parse the same
string. ``backend.entitlements`` is a sibling top-level package, not
``backend.infra``, so importing :class:`Tier` here is allowed by the
``engine is pure`` import-linter contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.entitlements.features import Tier


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _new_event_id() -> str:
    return uuid4().hex


@dataclass(frozen=True, kw_only=True)
class _BaseEvent:
    """Shared metadata. Concrete events extend this with their payload."""

    event_id: str = field(default_factory=_new_event_id)
    occurred_at: datetime = field(default_factory=_utc_now)
    correlation_id: str | None = None


@dataclass(frozen=True, kw_only=True)
class ForecastCompleted(_BaseEvent):
    """Engine pipeline finished and persisted artifacts for a job."""

    job_id: str
    user_id: str
    result_summary: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class AuditCompleted(_BaseEvent):
    """PDF extraction + variance computation finished for an audit."""

    audit_id: str
    user_id: str
    variance_score: float


@dataclass(frozen=True, kw_only=True)
class PaymentSucceeded(_BaseEvent):
    """Stripe webhook reported a successful checkout / invoice payment.

    ``stripe_event_id`` is the dedupe key — Stripe re-delivers a webhook
    on receiver timeout, so subscribers must idempotency-check against
    this value before mutating state.
    """

    user_id: str
    tier: Tier
    stripe_event_id: str


@dataclass(frozen=True, kw_only=True)
class PaymentRefunded(_BaseEvent):
    """Refund issued; entitlements should be revoked for the period."""

    user_id: str
    tier: Tier
    stripe_event_id: str


@dataclass(frozen=True, kw_only=True)
class UserDeleted(_BaseEvent):
    """User-initiated account deletion — cascades audit/PII purge."""

    user_id: str


__all__ = [
    "AuditCompleted",
    "ForecastCompleted",
    "PaymentRefunded",
    "PaymentSucceeded",
    "UserDeleted",
]
