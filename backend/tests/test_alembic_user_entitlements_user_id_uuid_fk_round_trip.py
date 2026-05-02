"""Alembic round-trip smoke for the user_entitlements.user_id UUID + FK migration.

Same shape as the other ``test_alembic_*_round_trip`` tests: structural
smoke inside the unit suite so a malformed revision shows up in a local
``pytest`` invocation rather than only in CI. Adds two ORM-side
assertions specific to this migration: ``user_entitlements.user_id``
is a UUID column with a foreign key to ``users.id`` ON DELETE CASCADE
so a Stripe webhook cannot grant a tier to a non-existent user.
"""

from __future__ import annotations

from alembic.script import ScriptDirectory
from sqlalchemy.dialects.postgresql import UUID

from backend.tests._alembic import assert_revision_in_chain

REVISION_ID = "b7e1c8d4a905"
PARENT_REVISION_ID = "9a1b2c3d4e5f"


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    assert_revision_in_chain(script, REVISION_ID, PARENT_REVISION_ID)


def test_user_entitlements_user_id_is_uuid_with_users_fk_cascade() -> None:
    """``user_entitlements.user_id`` is a UUID FK to ``users.id`` so a
    Stripe webhook cannot grant a tier to a non-existent user, and an
    account purge cascades to drop the entitlement rows."""
    from backend.db import Base

    table = Base.metadata.tables["user_entitlements"]
    column = table.c["user_id"]
    assert isinstance(column.type, UUID)
    (fk,) = column.foreign_keys
    assert fk.column.table.name == "users"
    assert fk.column.name == "id"
    assert fk.ondelete == "CASCADE"
