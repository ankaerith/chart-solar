"""Alembic round-trip smoke for the tmy_cache migration (chart-solar-wx1)."""

from __future__ import annotations

from alembic.script import ScriptDirectory

from backend.tests._alembic import assert_revision_in_chain

#: TMY cache revision under test — pinned by hash so a rename is caught.
TMY_CACHE_REVISION_ID = "a1f2c4d6b8e0"
PARENT_REVISION_ID = "8b3e7a1c4d20"


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    assert_revision_in_chain(script, TMY_CACHE_REVISION_ID, PARENT_REVISION_ID)


def test_orm_model_registers_on_metadata() -> None:
    from backend.db import Base

    assert "tmy_cache" in Base.metadata.tables
