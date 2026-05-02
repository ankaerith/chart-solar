"""Alembic round-trip smoke for the audits / installer_quotes migration."""

from __future__ import annotations

from alembic.script import ScriptDirectory

from backend.tests._alembic import assert_revision_in_chain

#: The audit-tables revision under test. Pinned by hash so the smoke
#: catches an accidental rename.
AUDIT_REVISION_ID = "8b3e7a1c4d20"
PARENT_REVISION_ID = "d4f1a2c8b9e3"


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    assert_revision_in_chain(script, AUDIT_REVISION_ID, PARENT_REVISION_ID)


def test_orm_models_register_on_metadata() -> None:
    """ORM ↔ migration parity: every table the migration creates is also
    registered on ``Base.metadata`` so test conftest can ``create_all``
    without touching alembic. Drift here means ``pytest`` and the alembic
    round-trip step would create different schemas."""
    from backend.db import Base

    expected = {"audits", "installer_quotes", "installers", "user_pii_vault"}
    actual = set(Base.metadata.tables.keys())
    assert expected.issubset(actual), f"missing ORM bindings for: {expected - actual}"
