"""Audit data model + privacy architecture ORM tables.

Implements the schema in ``PRODUCT_PLAN.md § Privacy architecture``. Asymmetric
by design: users are retained as anonymously as possible (PII isolated in
``user_pii_vault``, never joined directly to installer-derived data); installers
are retained in full because the moat is built on quote density per installer.

Per ADR 0005, ``installer_quotes.aggregation_opt_in`` defaults true; opt-out
cascades flip the column to false, which propagates through the public
``region_pricing_aggregates`` matview (created in the migration, no ORM
binding because it's read-only and the column set will evolve as the
``financials`` JSONB schema firms up).

The FK from ``audits.user_id`` and ``user_pii_vault.user_id`` to ``users.id``
lands in migration ``9a1b2c3d4e5f`` (chart-solar-n9rn). The cascade policies
are asymmetric: audits SET NULL (anonymized payload survives the account
delete) while user_pii_vault CASCADE (PII purges with the user).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class Installer(Base):
    """Canonical installer registry — retained in full, internal only.

    Sales-rep direct contact PII (phone, email) is stripped at extraction
    per LEGAL_CONSIDERATIONS.md F1; only company-level contact info lands
    here. Aliases + license numbers are JSONB to absorb the messy reality
    of how installers identify themselves across PDFs.
    """

    __tablename__ = "installers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_name: Mapped[str] = mapped_column(String(512), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default="{}")
    license_numbers: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    addresses: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, server_default="{}")
    phone: Mapped[str | None] = mapped_column(String(64))
    website: Mapped[str | None] = mapped_column(String(512))
    regions_operating: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    quotes_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    internal_notes: Mapped[str | None] = mapped_column(Text)


class UserPiiVault(Base):
    """Isolated PII storage; never joined to installer-derived data.

    The ``audits`` table holds an optional ``user_pii_vault_id`` link so
    one user can have multiple PII rows (e.g. "delete my historical data
    but keep this one"). Cascade behaviour is inverted from the obvious:
    deleting an audit nulls the link rather than deleting the vault row,
    and deleting a vault row preserves the audit (the audit's anonymized
    payload remains useful to the regional aggregate even after the
    user's name/email is purged).
    """

    __tablename__ = "user_pii_vault"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    full_name: Mapped[str | None] = mapped_column(String(512))
    address_full: Mapped[str | None] = mapped_column(String(1024))
    phone: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deletion_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Audit(Base):
    """User-facing audit record.

    ``user_id`` is nullable so anonymous (logged-out) audits still produce
    a row — the audit ID is the resource handle the user keeps in their
    URL bar even when there's no account behind it. ``location_bucket``
    is the coarse privacy bucket (ZIP-3 in US, postcode district in UK)
    that the regional aggregate matview groups by.
    """

    __tablename__ = "audits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    location_bucket: Mapped[str | None] = mapped_column(String(32))
    tariff_inputs: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    user_pii_vault_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_pii_vault.id", ondelete="SET NULL"),
    )


class InstallerQuote(Base):
    """One row per uploaded proposal PDF; installer-centric.

    Joins to ``audits`` (which carries the user link) and to the canonical
    ``installers`` row. Cascade rules:

    * ``audit_id`` ON DELETE CASCADE — when a user deletes their audit,
      the associated quotes go with it. The matview's nightly refresh
      then drops them from the regional aggregate.
    * ``installer_id`` ON DELETE RESTRICT — the installer registry is
      the moat; we never let a quote orphan a row by being deleted in
      a way that would also wipe an installer the registry depends on.

    ``aggregation_opt_in`` defaults true (per ADR 0005); per-user opt-out
    flips every quote whose audit's user_id matches.
    """

    __tablename__ = "installer_quotes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("installers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    raw_pdf_storage_url: Mapped[str | None] = mapped_column(String(1024))
    raw_pdf_sha256: Mapped[str | None] = mapped_column(String(64))
    raw_pdf_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    extraction_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending"
    )
    extraction_confidence: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    quote_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quote_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rep_name: Mapped[str | None] = mapped_column(String(256))

    location_country: Mapped[str | None] = mapped_column(String(2))
    location_region: Mapped[str | None] = mapped_column(String(8))
    location_bucket: Mapped[str | None] = mapped_column(String(32))

    system_spec: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    financials: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    quoted_metrics: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    our_forecast: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    variance_score: Mapped[float | None] = mapped_column(Float)

    aggregation_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
