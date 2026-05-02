"""Alembic round-trip smoke for the user_entitlements migration."""

from __future__ import annotations

from alembic.script import ScriptDirectory

from backend.tests._alembic import assert_revision_in_chain

ENTITLEMENTS_REVISION_ID = "f5a3b7c2d1e8"
PARENT_REVISION_ID = "a1f2c4d6b8e0"


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    assert_revision_in_chain(script, ENTITLEMENTS_REVISION_ID, PARENT_REVISION_ID)


def test_orm_model_registered_on_metadata() -> None:
    from backend.db import Base

    assert "user_entitlements" in Base.metadata.tables
