"""Auth tables backing the magic-link flow.

Three tables, one per concept:

* :class:`User` — minimal: id + email + created_at. The audit /
  installer_quotes / user_pii_vault tables already store ``user_id`` as
  a UUID without an FK (the FK lands in chart-solar-n9rn once auth is
  the source of truth for user identity); this table is the canonical
  side that backfill points at.
* :class:`MagicLink` — short-lived (15 min default) one-shot credentials.
  Stored hashed (sha256) so a leaked DB doesn't double as a leaked auth
  link. ``consumed_at`` marks the row terminally used; the consume path
  refuses re-use even before TTL expiry.
* :class:`Session` — long-lived browser session. Stored hashed for the
  same reason as ``MagicLink``; the cookie carries the raw token.
  ``revoked_at`` is the sign-out / global-revoke seam.

User id never appears in URLs or logs — the magic-link token + the
session token are the only client-facing identifiers, and both are
opaque random strings.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class User(Base):
    """Canonical user row — magic-link auth holds no other PII here.

    The user's name / address / phone live in
    :class:`backend.db.audit_models.UserPiiVault` and are linked from
    audits, not from this table; this row remains unjoined to PII so
    operator tooling can list active users without touching PII.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    # Per-user override on ADR 0005's default-ON aggregation; cascade
    # to ``installer_quotes.aggregation_opt_in`` lives in ``audit_service``.
    aggregation_opt_out: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )


class MagicLink(Base):
    """One-shot magic-link credential, expires + consumes terminally.

    The token is SHA-256-hashed at write time (``token_hash``); the raw
    token is only ever held in the email body that goes to the user.
    A leaked DB therefore can't be used to forge auth links.
    """

    __tablename__ = "magic_links"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Session(Base):
    """Long-lived browser session, hashed at rest.

    The cookie carries the raw token; the DB stores SHA-256 of it.
    ``revoked_at`` is the sign-out + admin-kick seam; sessions are
    valid iff ``revoked_at IS NULL AND expires_at > now()``.
    """

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
