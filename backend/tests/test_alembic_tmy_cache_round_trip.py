"""Alembic round-trip smoke for the tmy_cache migration (chart-solar-wx1).

Same shape as ``test_alembic_audits_round_trip``: assert the migration
is wired into the chain, has working upgrade/downgrade callables, and
that ``Base.metadata`` registers every table the migration creates so
conftest's ``create_all`` doesn't drift from production DDL.
"""

from __future__ import annotations

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

#: TMY cache revision under test — pinned by hash so a rename is caught.
TMY_CACHE_REVISION_ID = "a1f2c4d6b8e0"
PARENT_REVISION_ID = "8b3e7a1c4d20"


@pytest.fixture(scope="module")
def script() -> ScriptDirectory:
    cfg = Config("alembic.ini")
    return ScriptDirectory.from_config(cfg)


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    revision = script.get_revision(TMY_CACHE_REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PARENT_REVISION_ID


def test_migration_exposes_upgrade_and_downgrade(script: ScriptDirectory) -> None:
    revision = script.get_revision(TMY_CACHE_REVISION_ID)
    assert revision is not None
    module = revision.module
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert module.revision == TMY_CACHE_REVISION_ID
    assert module.down_revision == PARENT_REVISION_ID


def test_orm_model_registers_on_metadata() -> None:
    from backend.db import Base

    assert "tmy_cache" in Base.metadata.tables
