"""Alembic round-trip smoke for the user_entitlements migration.

Same shape as ``test_alembic_audits_round_trip.py``: structural smoke
inside the unit suite so a malformed revision shows up in a local
``pytest`` invocation rather than only in CI.
"""

from __future__ import annotations

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

ENTITLEMENTS_REVISION_ID = "f5a3b7c2d1e8"
PARENT_REVISION_ID = "a1f2c4d6b8e0"


@pytest.fixture(scope="module")
def script() -> ScriptDirectory:
    cfg = Config("alembic.ini")
    return ScriptDirectory.from_config(cfg)


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    revision = script.get_revision(ENTITLEMENTS_REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PARENT_REVISION_ID


def test_migration_exposes_upgrade_and_downgrade(script: ScriptDirectory) -> None:
    revision = script.get_revision(ENTITLEMENTS_REVISION_ID)
    assert revision is not None
    module = revision.module
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert module.revision == ENTITLEMENTS_REVISION_ID
    assert module.down_revision == PARENT_REVISION_ID


def test_orm_model_registered_on_metadata() -> None:
    from backend.db import Base

    assert "user_entitlements" in Base.metadata.tables
