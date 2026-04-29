"""baseline

Revision ID: c6cb527d3505
Revises:
Create Date: 2026-04-28 21:44:15.931476

Empty baseline so subsequent migrations have a parent revision. Schema-bearing
migrations land on top of this one as Phase 1 tables (audits, installer_quotes,
installers, user_pii_vault, region_pricing_aggregates, installer_internal_stats)
arrive.

"""

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401  (kept for stub parity with future migrations)
from alembic import op  # noqa: F401

revision: str = "c6cb527d3505"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
