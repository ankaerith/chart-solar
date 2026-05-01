"""Alembic round-trip smoke for the users / magic_links / sessions migration."""

from __future__ import annotations

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

AUTH_REVISION_ID = "a8b2c4d6e9f1"
PARENT_REVISION_ID = "8b3e7a1c4d20"


@pytest.fixture(scope="module")
def script() -> ScriptDirectory:
    cfg = Config("alembic.ini")
    return ScriptDirectory.from_config(cfg)


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    revision = script.get_revision(AUTH_REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PARENT_REVISION_ID


def test_migration_exposes_upgrade_and_downgrade(script: ScriptDirectory) -> None:
    revision = script.get_revision(AUTH_REVISION_ID)
    assert revision is not None
    module = revision.module
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert module.revision == AUTH_REVISION_ID
    assert module.down_revision == PARENT_REVISION_ID


def test_orm_models_register_on_metadata() -> None:
    from backend.db import Base

    expected = {"users", "magic_links", "sessions"}
    actual = set(Base.metadata.tables.keys())
    assert expected.issubset(actual), f"missing ORM bindings for: {expected - actual}"
