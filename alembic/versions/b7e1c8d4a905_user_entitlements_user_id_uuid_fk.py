"""user_entitlements.user_id → UUID + FK to users.id

Revision ID: b7e1c8d4a905
Revises: 9a1b2c3d4e5f
Create Date: 2026-05-02 09:00:00.000000

The original ``user_entitlements`` migration (``f5a3b7c2d1e8``) created
``user_id`` as a free-form ``String(255)`` because the auth migration
was gated. The users table now exists and the FK can be wired up.

This is a security fix: the Stripe webhook subscriber writes
``metadata.user_id`` from the inbound payload directly to this column,
so without an FK any caller that can craft a Stripe event with
arbitrary metadata can grant a paid tier to any string id — including
one that belongs to no user, or that conflicts with a future user id.
The FK forces grant_tier to refuse non-existent users at the database
level; ``ON DELETE CASCADE`` keeps the entitlement ledger consistent
with account deletion.

Pre-launch — no production rows yet — so the type swap is unconditional.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "b7e1c8d4a905"
down_revision: str | Sequence[str] | None = "9a1b2c3d4e5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAME = "fk_user_entitlements_user_id_users"
_INDEX_NAME = "ix_user_entitlements_user_id"


def upgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="user_entitlements")
    op.alter_column(
        "user_entitlements",
        "user_id",
        type_=UUID(as_uuid=True),
        existing_type=sa.String(length=255),
        existing_nullable=False,
        postgresql_using="user_id::uuid",
    )
    op.create_foreign_key(
        _FK_NAME,
        source_table="user_entitlements",
        referent_table="users",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )
    op.create_index(_INDEX_NAME, "user_entitlements", ["user_id"])


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="user_entitlements")
    op.drop_constraint(_FK_NAME, "user_entitlements", type_="foreignkey")
    op.alter_column(
        "user_entitlements",
        "user_id",
        type_=sa.String(length=255),
        existing_type=UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using="user_id::text",
    )
    op.create_index(_INDEX_NAME, "user_entitlements", ["user_id"])
