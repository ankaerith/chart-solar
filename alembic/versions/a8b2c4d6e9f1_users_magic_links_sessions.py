"""users + magic_links + sessions

Revision ID: a8b2c4d6e9f1
Revises: a1f2c4d6b8e0
Create Date: 2026-04-30 23:30:00.000000

Auth tables backing the magic-link flow (chart-solar-ij9). Tokens are
hashed at rest (sha256); only the email body holds the raw value.
``sessions.user_id`` has FK ``ondelete=CASCADE`` so a user-deletion
sweep takes their sessions with it. The audit-side FK from
``audits.user_id`` to ``users.id`` lands separately in
chart-solar-n9rn (post-auth) so this migration stays minimal.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "a8b2c4d6e9f1"
down_revision: str | Sequence[str] | None = "a1f2c4d6b8e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "magic_links",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_magic_links_email",
        "magic_links",
        ["email"],
    )

    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_sessions_user_id",
        "sessions",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_magic_links_email", table_name="magic_links")
    op.drop_table("magic_links")
    op.drop_table("users")
