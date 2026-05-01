"""user_entitlements

Revision ID: f5a3b7c2d1e8
Revises: a1f2c4d6b8e0
Create Date: 2026-04-30 23:00:00.000000

Backs ``backend.services.entitlements_grants`` — one row per (user,
tier, granting Stripe event). The unique constraint on
``granted_by_event_id`` is the database-level idempotency that pairs
with the in-memory event-bus dedupe so a worker re-delivering after a
crash can't double-grant. Refunds set ``revoked_at`` (and record the
refund's Stripe event id on ``revoked_by_event_id``) rather than
deleting; the audit trail of "who held what tier when" stays intact.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "f5a3b7c2d1e8"
down_revision: str | Sequence[str] | None = "a1f2c4d6b8e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_entitlements",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("tier", sa.String(length=64), nullable=False),
        sa.Column(
            "granted_by_event_id",
            sa.String(length=255),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_by_event_id", sa.String(length=255), unique=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_user_entitlements_user_id",
        "user_entitlements",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_entitlements_user_id", table_name="user_entitlements")
    op.drop_table("user_entitlements")
