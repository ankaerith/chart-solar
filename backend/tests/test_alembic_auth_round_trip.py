"""Alembic round-trip smoke for the users / magic_links / sessions migration."""

from __future__ import annotations

from alembic.script import ScriptDirectory

from backend.tests._alembic import assert_revision_in_chain

AUTH_REVISION_ID = "a8b2c4d6e9f1"
PARENT_REVISION_ID = "f5a3b7c2d1e8"


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    assert_revision_in_chain(script, AUTH_REVISION_ID, PARENT_REVISION_ID)


def test_orm_models_register_on_metadata() -> None:
    from backend.db import Base

    expected = {"users", "magic_links", "sessions"}
    actual = set(Base.metadata.tables.keys())
    assert expected.issubset(actual), f"missing ORM bindings for: {expected - actual}"
