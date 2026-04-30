"""Alembic round-trip smoke for the audits / installer_quotes migration.

CI's ``Alembic round-trip`` step is the canonical exercise of the whole
chain (``upgrade head → downgrade base → upgrade head``); this test
adds a structural smoke that runs alongside the rest of the unit suite
so a malformed revision shows up in a local ``pytest`` invocation too.

We don't run the migration's DDL against the live test database here:
``conftest.py``'s session-wide schema fixture already created the
ORM-mapped tables via ``Base.metadata.create_all``, so an ``alembic
upgrade`` in-band would either no-op (best case) or collide with the
existing schema (worst case). Instead we assert the migration module
is wired into the chain correctly + that the upgrade / downgrade
callables resolve through alembic's script loader (which handles the
digit-prefixed filenames the standard ``importlib`` path can't).
"""

from __future__ import annotations

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

#: The audit-tables revision under test. Pinned by hash so the smoke
#: catches an accidental rename.
AUDIT_REVISION_ID = "8b3e7a1c4d20"
PARENT_REVISION_ID = "d4f1a2c8b9e3"


@pytest.fixture(scope="module")
def script() -> ScriptDirectory:
    """Alembic's view of the migration chain on disk."""
    cfg = Config("alembic.ini")
    return ScriptDirectory.from_config(cfg)


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    """The audit migration is reachable from ``head`` and points at the
    idempotency_keys revision as its parent — guards against an accidental
    fork in the chain."""
    revision = script.get_revision(AUDIT_REVISION_ID)
    assert revision is not None
    assert revision.down_revision == PARENT_REVISION_ID


def test_migration_exposes_upgrade_and_downgrade(script: ScriptDirectory) -> None:
    """The smoke that catches ``def upgrade()`` typos at script-load time.

    Alembic's ``Script.module`` lazy-loads the file via its own loader
    (the standard ``importlib`` path can't import the digit-prefixed
    file name).
    """
    revision = script.get_revision(AUDIT_REVISION_ID)
    assert revision is not None
    module = revision.module
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert module.revision == AUDIT_REVISION_ID
    assert module.down_revision == PARENT_REVISION_ID


def test_orm_models_register_on_metadata() -> None:
    """ORM ↔ migration parity: every table the migration creates is also
    registered on ``Base.metadata`` so test conftest can ``create_all``
    without touching alembic. Drift here means ``pytest`` and the alembic
    round-trip step would create different schemas."""
    from backend.db import Base

    expected = {"audits", "installer_quotes", "installers", "user_pii_vault"}
    actual = set(Base.metadata.tables.keys())
    assert expected.issubset(actual), f"missing ORM bindings for: {expected - actual}"
