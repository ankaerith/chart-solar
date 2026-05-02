"""user_entitlements.tier CHECK constraint

Revision ID: b3c2d1e8f9a4
Revises: a8b2c4d6e9f1
Create Date: 2026-05-01 18:00:00.000000

Adds a database-level CHECK on ``user_entitlements.tier`` so a column
write outside the known ``Tier`` enum can't land. Pairs with dropping
the defensive ``try Tier(raw) except``-to-FREE in
``backend.services.entitlements_grants.tier_for_user`` — the parse
existed to absorb a hypothetical legacy row, which the constraint
now makes impossible at insert time.

Trade-off (carried over from chart-solar-kuiu): renaming or removing
a ``Tier`` enum member is now a coordinated change — the constraint
must be dropped, rows migrated, and the constraint recreated. Adding
a new tier value is a constraint-only update (one ALTER TABLE).
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
