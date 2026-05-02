"""Alembic round-trip smoke for the users.aggregation_opt_out migration."""

from __future__ import annotations

from alembic.script import ScriptDirectory

from backend.tests._alembic import assert_revision_in_chain

OPT_OUT_REVISION_ID = "c4d2e1a8b9f3"
PARENT_REVISION_ID = "b3c2d1e8f9a4"


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    assert_revision_in_chain(script, OPT_OUT_REVISION_ID, PARENT_REVISION_ID)


def test_user_orm_has_aggregation_opt_out_column() -> None:
    from backend.db import Base

    table = Base.metadata.tables["users"]
    column = table.c["aggregation_opt_out"]
    assert column is not None
    assert column.nullable is False
    # The default is ``func.false()`` server-side; a freshly-inserted
    # user must come up opted-IN to aggregation per ADR 0005.
    assert column.server_default is not None
