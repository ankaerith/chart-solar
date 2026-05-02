"""Shared helpers for backend/tests/test_alembic_*_round_trip.py.

Each per-migration smoke asserts the revision is in the chain (right
parent, callable upgrade/downgrade) — only the migration-specific bits
(column nullability, CHECK constraint registered, etc.) are unique.
This module hoists the shared assertion; the ``script`` fixture lives
in ``conftest.py`` so every per-migration file picks it up by name.

CI's ``Alembic round-trip`` step is the canonical exercise of the
whole chain (``upgrade head → downgrade base → upgrade head``); these
smokes run alongside the rest of the unit suite so a malformed revision
shows up in a local ``pytest`` invocation too.

We don't run the migration's DDL against the live test database here:
``conftest.py``'s session-wide schema fixture already created the
ORM-mapped tables via ``Base.metadata.create_all``, so an ``alembic
upgrade`` in-band would either no-op or collide. The structural
assertions below catch the failure modes the round-trip step would
also catch (revision missing, chain forked, upgrade/downgrade typo)
without paying for the full DDL replay.
"""

from __future__ import annotations

from alembic.script import ScriptDirectory


def assert_revision_in_chain(
    script: ScriptDirectory,
    revision_id: str,
    parent_id: str,
) -> None:
    """Assert ``revision_id`` is reachable with ``parent_id`` as its
    ``down_revision``, and that its module exposes callable
    ``upgrade`` / ``downgrade`` functions.

    Catches three classes of breakage from a single call: revision
    file removed or renamed (``script.get_revision`` returns ``None``),
    chain forked (``down_revision`` mismatch), or ``def upgrade`` /
    ``def downgrade`` typo at script-load time. Alembic's
    ``Script.module`` lazy-loads the file via its own loader (the
    standard ``importlib`` path can't import the digit-prefixed
    filename), which is why we go through it rather than ``importlib``.
    """
    revision = script.get_revision(revision_id)
    assert revision is not None, f"revision {revision_id} not in chain"
    assert revision.down_revision == parent_id, (
        f"expected down_revision={parent_id}, got {revision.down_revision}"
    )
    module = revision.module
    assert callable(module.upgrade)
    assert callable(module.downgrade)
    assert module.revision == revision_id
    assert module.down_revision == parent_id
