"""index installer_quotes.audit_id

Revision ID: e2c5b9a7d3f4
Revises: c4d2e1a8b9f3
Create Date: 2026-05-01 20:00:00.000000

Adds a btree index on ``installer_quotes.audit_id`` to support the
hot-path filter on the FK. Two callers rely on this:

* ``ON DELETE CASCADE`` from ``audits.id`` — Postgres needs the index on
  the child column to avoid a sequential scan when the parent row is
  deleted.
* ``backend.services.audit_service.set_user_aggregation_opt_out`` — flips
  ``aggregation_opt_in`` on every quote whose audit belongs to the user;
  the SQL is a correlated subquery against ``audit_id``.

``installer_id`` is already indexed because the ORM column has
``index=True``; this matches it for the other FK.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e2c5b9a7d3f4"
down_revision: str | Sequence[str] | None = "c4d2e1a8b9f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_installer_quotes_audit_id",
        "installer_quotes",
        ["audit_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_installer_quotes_audit_id", table_name="installer_quotes")
