"""user_entitlements.tier CHECK constraint

Revision ID: b3c2d1e8f9a4
Revises: a8b2c4d6e9f1
Create Date: 2026-05-01 18:00:00.000000

Adds a database-level CHECK on ``user_entitlements.tier`` so a write
outside the known ``Tier`` enum can't land. Renaming or removing a
``Tier`` member becomes a coordinated migration (drop constraint,
migrate rows, recreate); adding a tier is a one-statement ALTER.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b3c2d1e8f9a4"
down_revision: str | Sequence[str] | None = "a8b2c4d6e9f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "ck_user_entitlements_tier"
ALLOWED_TIERS = ("free", "decision_pack", "founders", "track")


def upgrade() -> None:
    allowed_sql = ", ".join(f"'{value}'" for value in ALLOWED_TIERS)
    op.create_check_constraint(
        CONSTRAINT_NAME,
        "user_entitlements",
        f"tier IN ({allowed_sql})",
    )


def downgrade() -> None:
    op.drop_constraint(CONSTRAINT_NAME, "user_entitlements", type_="check")
