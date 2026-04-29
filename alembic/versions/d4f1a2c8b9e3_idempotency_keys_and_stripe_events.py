"""idempotency_keys + stripe_events

Revision ID: d4f1a2c8b9e3
Revises: c6cb527d3505
Create Date: 2026-04-29 12:00:00.000000

Tables backing `backend/infra/idempotency.py`:

* `idempotency_keys` — request → response cache for any mutating POST that
  opts in via `@idempotent`. Composite PK (`key`, `route`) lets two routes
  share a client-supplied `Idempotency-Key` without collision; `request_hash`
  rejects mismatched bodies (HTTP 409); `expires_at` is the reaper boundary.

* `stripe_events` — webhook dedupe ledger keyed on Stripe's `event.id`,
  so an entitlement grant happens exactly once even if Stripe retries.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f1a2c8b9e3"
down_revision: str | Sequence[str] | None = "c6cb527d3505"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("route", sa.String(length=255), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.SmallInteger(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", "route", name="pk_idempotency_keys"),
    )
    op.create_index(
        "ix_idempotency_keys_expires_at",
        "idempotency_keys",
        ["expires_at"],
    )

    op.create_table(
        "stripe_events",
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("stripe_events")
    op.drop_index("ix_idempotency_keys_expires_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
