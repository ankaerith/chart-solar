"""users FK on audits.user_id + user_pii_vault.user_id

Revision ID: 9a1b2c3d4e5f
Revises: e2c5b9a7d3f4
Create Date: 2026-05-01 21:00:00.000000

The audit-tables migration (chart-solar-0hl, ``8b3e7a1c4d20``) created
``audits.user_id`` and ``user_pii_vault.user_id`` as bare UUID columns
because the auth migration was gated. The users table now exists
(``a8b2c4d6e9f1``), so wire up the FK constraints with the asymmetric
delete policies the privacy architecture calls for:

* ``audits.user_id`` ON DELETE SET NULL — the audit's anonymized
  payload remains useful to the regional aggregate even after the
  user's account is purged. The link goes; the row stays.
* ``user_pii_vault.user_id`` ON DELETE CASCADE — PII purges with the
  user. There is no scenario where a deleted-account PII row should
  survive the deletion event.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9a1b2c3d4e5f"
down_revision: str | Sequence[str] | None = "e2c5b9a7d3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_AUDITS_FK = "fk_audits_user_id_users"
_PII_FK = "fk_user_pii_vault_user_id_users"


def upgrade() -> None:
    op.create_foreign_key(
        _AUDITS_FK,
        source_table="audits",
        referent_table="users",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        _PII_FK,
        source_table="user_pii_vault",
        referent_table="users",
        local_cols=["user_id"],
        remote_cols=["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(_PII_FK, "user_pii_vault", type_="foreignkey")
    op.drop_constraint(_AUDITS_FK, "audits", type_="foreignkey")
