"""Alembic round-trip smoke for the installer_quotes.audit_id index migration."""

from __future__ import annotations

from alembic.script import ScriptDirectory

from backend.tests._alembic import assert_revision_in_chain

INDEX_REVISION_ID = "e2c5b9a7d3f4"
PARENT_REVISION_ID = "c4d2e1a8b9f3"


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    assert_revision_in_chain(script, INDEX_REVISION_ID, PARENT_REVISION_ID)


def test_installer_quotes_audit_id_is_indexed_in_orm() -> None:
    from backend.db import Base

    table = Base.metadata.tables["installer_quotes"]
    indexed_columns = {tuple(idx.columns.keys()) for idx in table.indexes}
    assert ("audit_id",) in indexed_columns
