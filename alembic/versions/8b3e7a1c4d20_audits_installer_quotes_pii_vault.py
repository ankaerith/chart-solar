"""audits + installer_quotes + installers + user_pii_vault + matviews

Revision ID: 8b3e7a1c4d20
Revises: d4f1a2c8b9e3
Create Date: 2026-04-29 18:30:00.000000

Implements the data model from PRODUCT_PLAN.md § Privacy architecture
(chart-solar-0hl). The schema is asymmetric by design — installer rows
are retained in full for moat-building, user PII is isolated in its
own table so the user can purge their identity without losing the
anonymized audit payload that feeds the regional aggregate.

Key cascade choices:

* ``installer_quotes.audit_id`` ON DELETE CASCADE — user-initiated audit
  deletion drops the quotes too. The matview's nightly refresh then
  removes them from ``region_pricing_aggregates``.
* ``installer_quotes.installer_id`` ON DELETE RESTRICT — the canonical
  installer row is the moat; we never let an accidental delete cascade
  through quote orphans.
* ``audits.user_pii_vault_id`` ON DELETE SET NULL — purging a user's
  PII vault row leaves the audit intact (its anonymized payload stays
  useful to aggregates); deleting the audit nulls the link rather than
  cascading into the vault.

There is no FK to a ``users`` table here — the auth migration is gated
on chart-solar-bcy. ``user_id`` columns are typed UUID + indexed; the
FK constraint is added in a follow-up migration once ``users`` exists.

The two materialized views (``region_pricing_aggregates`` and
``installer_internal_stats``) are intentionally minimal: just counts +
median $/W until the ``financials`` JSONB schema firms up. They live
in the migration as raw SQL because SQLAlchemy doesn't model matviews
natively. ``CONCURRENTLY`` is omitted on the unique indexes so the
upgrade can run inside the migration's transaction.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8b3e7a1c4d20"
down_revision: str | Sequence[str] | None = "d4f1a2c8b9e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "installers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("canonical_name", sa.String(length=512), nullable=False),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "license_numbers",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "addresses",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column(
            "regions_operating",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("quotes_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("internal_notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "user_pii_vault",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=512), nullable=True),
        sa.Column("address_full", sa.String(length=1024), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deletion_scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_user_pii_vault_user_id",
        "user_pii_vault",
        ["user_id"],
    )

    op.create_table(
        "audits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("location_bucket", sa.String(length=32), nullable=True),
        sa.Column(
            "tariff_inputs",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "user_pii_vault_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_pii_vault.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_audits_user_id", "audits", ["user_id"])

    op.create_table(
        "installer_quotes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "installer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("installers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("raw_pdf_storage_url", sa.String(length=1024), nullable=True),
        sa.Column("raw_pdf_sha256", sa.String(length=64), nullable=True),
        sa.Column("raw_pdf_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "extraction_status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "extraction_confidence",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("quote_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quote_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rep_name", sa.String(length=256), nullable=True),
        sa.Column("location_country", sa.String(length=2), nullable=True),
        sa.Column("location_region", sa.String(length=8), nullable=True),
        sa.Column("location_bucket", sa.String(length=32), nullable=True),
        sa.Column(
            "system_spec",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "financials",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "quoted_metrics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "our_forecast",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("variance_score", sa.Float(), nullable=True),
        sa.Column(
            "aggregation_opt_in",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.create_index(
        "ix_installer_quotes_installer_id",
        "installer_quotes",
        ["installer_id"],
    )

    # Region pricing aggregate matview — public, refreshed nightly. Filters
    # to opted-in quotes with a parsed gross_per_watt only. Currency comes
    # from the financials JSON so a single matview can hold USD + GBP rows.
    op.execute(
        """
        CREATE MATERIALIZED VIEW region_pricing_aggregates AS
        WITH q AS (
            SELECT
                location_bucket AS region_key,
                COALESCE(financials ->> 'currency', 'USD') AS currency,
                ((financials ->> 'gross_per_watt')::numeric) AS dollar_per_watt
            FROM installer_quotes
            WHERE aggregation_opt_in = true
              AND location_bucket IS NOT NULL
              AND (financials ? 'gross_per_watt')
        )
        SELECT
            region_key,
            currency,
            COUNT(*) AS n_quotes,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY dollar_per_watt)
              AS median_dollar_per_watt,
            PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY dollar_per_watt) AS p10,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY dollar_per_watt) AS p25,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY dollar_per_watt) AS p75,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY dollar_per_watt) AS p90,
            NOW() AS last_updated
        FROM q
        GROUP BY region_key, currency
        WITH NO DATA
        """
    )
    # Unique index on (region_key, currency) is required for REFRESH
    # MATERIALIZED VIEW CONCURRENTLY in production.
    op.create_index(
        "ix_region_pricing_aggregates_region_key",
        "region_pricing_aggregates",
        ["region_key", "currency"],
        unique=True,
    )

    # Installer internal-stats matview — INTERNAL ONLY, never exposed.
    # Minimal column set until the financials JSONB schema firms up;
    # variance_score → median_year1_overstatement_pct lands once
    # our_forecast carries that derived field.
    op.execute(
        """
        CREATE MATERIALIZED VIEW installer_internal_stats AS
        SELECT
            installer_id,
            COUNT(*) AS n_quotes,
            PERCENTILE_CONT(0.50) WITHIN GROUP (
                ORDER BY ((financials ->> 'gross_per_watt')::numeric)
            ) FILTER (WHERE financials ? 'gross_per_watt') AS median_dollar_per_watt,
            AVG(variance_score) FILTER (WHERE variance_score IS NOT NULL)
              AS mean_variance_score,
            NOW() AS last_updated
        FROM installer_quotes
        GROUP BY installer_id
        WITH NO DATA
        """
    )
    op.create_index(
        "ix_installer_internal_stats_installer_id",
        "installer_internal_stats",
        ["installer_id"],
        unique=True,
    )


def downgrade() -> None:
    # Drop in reverse FK + matview dependency order. The matviews go
    # first because they depend on installer_quotes; installer_quotes
    # depends on audits + installers; audits depends on user_pii_vault.
    op.execute("DROP MATERIALIZED VIEW IF EXISTS installer_internal_stats")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS region_pricing_aggregates")
    op.drop_index("ix_installer_quotes_installer_id", table_name="installer_quotes")
    op.drop_table("installer_quotes")
    op.drop_index("ix_audits_user_id", table_name="audits")
    op.drop_table("audits")
    op.drop_index("ix_user_pii_vault_user_id", table_name="user_pii_vault")
    op.drop_table("user_pii_vault")
    op.drop_table("installers")
