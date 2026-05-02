"""Alembic round-trip smoke for the users FK migration (chart-solar-n9rn).

Same shape as the other ``test_alembic_*_round_trip`` tests: structural
smoke inside the unit suite so a malformed revision shows up in a local
``pytest`` invocation rather than only in CI. Adds two ORM-side
assertions specific to this migration: ``audits.user_id`` and
``user_pii_vault.user_id`` each carry a foreign key to ``users.id``
with the asymmetric ondelete policies the privacy architecture calls
for (SET NULL on audits, CASCADE on user_pii_vault).
"""

from __future__ import annotations

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

USERS_FK_REVISION_ID = "9a1b2c3d4e5f"
PARENT_REVISION_ID = "e2c5b9a7d3f4"


@pytest.fixture(scope="module")
def script() -> ScriptDirectory:
    cfg = Config("alembic.ini")
    return ScriptDirectory.from_config(cfg)


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    revision = script.get_revision(USERS_FK_REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PARENT_REVISION_ID


def test_migration_exposes_upgrade_and_downgrade(script: ScriptDirectory) -> None:
    revision = script.get_revision(USERS_FK_REVISION_ID)
    assert revision is not None
    module = revision.module
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert module.revision == USERS_FK_REVISION_ID
    assert module.down_revision == PARENT_REVISION_ID


def test_audits_user_id_fk_is_set_null() -> None:
    """``audits.user_id`` references ``users.id`` and SET NULL preserves
    the anonymized audit payload when the user account is deleted."""
    from backend.db import Base

    table = Base.metadata.tables["audits"]
    # Tuple-unpack also asserts there's exactly one FK on the column.
    (fk,) = table.c["user_id"].foreign_keys
    assert fk.column.table.name == "users"
    assert fk.column.name == "id"
    assert fk.ondelete == "SET NULL"


def test_user_pii_vault_user_id_fk_is_cascade() -> None:
    """``user_pii_vault.user_id`` references ``users.id`` and CASCADE
    deletes the PII row when the user account is purged."""
    from backend.db import Base

    table = Base.metadata.tables["user_pii_vault"]
    (fk,) = table.c["user_id"].foreign_keys
    assert fk.column.table.name == "users"
    assert fk.column.name == "id"
    assert fk.ondelete == "CASCADE"
