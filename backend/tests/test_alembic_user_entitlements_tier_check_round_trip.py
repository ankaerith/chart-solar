"""Alembic round-trip smoke for the user_entitlements.tier CHECK migration."""

from __future__ import annotations

from alembic.script import ScriptDirectory

from backend.tests._alembic import assert_revision_in_chain

TIER_CHECK_REVISION_ID = "b3c2d1e8f9a4"
PARENT_REVISION_ID = "a8b2c4d6e9f1"


def test_migration_is_in_chain(script: ScriptDirectory) -> None:
    assert_revision_in_chain(script, TIER_CHECK_REVISION_ID, PARENT_REVISION_ID)


def test_check_constraint_registered_on_metadata() -> None:
    from backend.db import Base

    table = Base.metadata.tables["user_entitlements"]
    constraint_names = {c.name for c in table.constraints}
    assert "ck_user_entitlements_tier" in constraint_names


def test_check_constraint_covers_every_known_tier() -> None:
    """The constraint hard-codes tier values; if a Tier member is added
    without updating the migration + model, this catches it."""
    from sqlalchemy import CheckConstraint

    from backend.db import Base
    from backend.entitlements.features import Tier

    table = Base.metadata.tables["user_entitlements"]
    check = next(
        c
        for c in table.constraints
        if isinstance(c, CheckConstraint) and c.name == "ck_user_entitlements_tier"
    )
    sql = str(check.sqltext)
    for member in Tier:
        assert f"'{member.value}'" in sql
