"""Alembic round-trip smoke for the installer_quotes.audit_id index migration.

Same shape as the other ``test_alembic_*_round_trip`` tests: structural
smoke inside the unit suite so a malformed revision shows up in a local
``pytest`` invocation rather than only in CI.
"""

from __future__ import annotations

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

INDEX_REVISION_ID = "e2c5b9a7d3f4"
PARENT_REVISION_ID = "c4d2e1a8b9f3"


@pytest.fixture(scope="module")
def script() -> ScriptDirectory:
    cfg = Config("alembic.ini")
    return ScriptDirectory.from_config(cfg)


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    revision = script.get_revision(INDEX_REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PARENT_REVISION_ID


def test_migration_exposes_upgrade_and_downgrade(script: ScriptDirectory) -> None:
    revision = script.get_revision(INDEX_REVISION_ID)
    assert revision is not None
    module = revision.module
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert module.revision == INDEX_REVISION_ID
    assert module.down_revision == PARENT_REVISION_ID


def test_installer_quotes_audit_id_is_indexed_in_orm() -> None:
    from backend.db import Base

    table = Base.metadata.tables["installer_quotes"]
    indexed_columns = {tuple(idx.columns.keys()) for idx in table.indexes}
    assert ("audit_id",) in indexed_columns
