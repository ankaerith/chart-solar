"""Alembic round-trip smoke for the users.aggregation_opt_out migration.

Same shape as the other ``test_alembic_*_round_trip`` tests: structural
smoke inside the unit suite so a malformed revision shows up in a local
``pytest`` invocation rather than only in CI.
"""

from __future__ import annotations

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

OPT_OUT_REVISION_ID = "c4d2e1a8b9f3"
PARENT_REVISION_ID = "a8b2c4d6e9f1"


@pytest.fixture(scope="module")
def script() -> ScriptDirectory:
    cfg = Config("alembic.ini")
    return ScriptDirectory.from_config(cfg)


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    revision = script.get_revision(OPT_OUT_REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PARENT_REVISION_ID


def test_migration_exposes_upgrade_and_downgrade(script: ScriptDirectory) -> None:
    revision = script.get_revision(OPT_OUT_REVISION_ID)
    assert revision is not None
    module = revision.module
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert module.revision == OPT_OUT_REVISION_ID
    assert module.down_revision == PARENT_REVISION_ID


def test_user_orm_has_aggregation_opt_out_column() -> None:
    from backend.db import Base

    table = Base.metadata.tables["users"]
    column = table.c["aggregation_opt_out"]
    assert column is not None
    assert column.nullable is False
    # The default is ``func.false()`` server-side; a freshly-inserted
    # user must come up opted-IN to aggregation per ADR 0005.
    assert column.server_default is not None
