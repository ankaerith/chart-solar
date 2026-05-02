"""users.aggregation_opt_out column

Revision ID: c4d2e1a8b9f3
Revises: a8b2c4d6e9f1
Create Date: 2026-05-01 19:00:00.000000

Adds the per-user opt-out flag introduced in
`docs/adr/0005-aggregation-default-on-no-ui.md`. ``installer_quotes``
already defaults ``aggregation_opt_in = true`` (set in the audits
migration), so the only schema delta here is the new user-level
boolean. Phase 1 has no UI surface; ``PATCH /api/me/aggregation``
flips this flag and the cascade lives in
``backend.services.audit_service.set_user_aggregation_opt_out``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d2e1a8b9f3"
down_revision: str | Sequence[str] | None = "a8b2c4d6e9f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "aggregation_opt_out",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "aggregation_opt_out")
