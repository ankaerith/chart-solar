"""Audit + PII vault read / delete service.

Two distinct deletion semantics, mirroring the cascade rules in
``backend.db.audit_models``:

* Deleting an :class:`Audit` cascades to its ``installer_quotes`` (FK
  ``ondelete="CASCADE"`` on ``audit_id``) and nulls the link from the
  audit to the user's PII vault row (``ondelete="SET NULL"`` on
  ``audits.user_pii_vault_id``). The PII vault row itself is preserved
  — independent deletion below.
* Deleting a :class:`UserPiiVault` row drops the user's PII outright
  but preserves any audits that referenced it (the FK ``SET NULL``
  fires on the audit side, leaving the audit's anonymized payload
  available to the regional aggregate matview).

Both helpers are owner-aware: the caller passes ``user_id`` and the
service applies it as a WHERE clause so a missing-or-not-owned row
returns ``False`` (the route layer translates that to 404). Nothing
in this module short-circuits via ``HTTPException`` — that stays in
``backend.api.*``.
"""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.audit_models import Audit, UserPiiVault
from backend.infra.logging import get_logger

_log = get_logger(__name__)


async def find_audit_owned_by(
    session: AsyncSession,
    *,
    audit_id: uuid.UUID,
    user_id: str,
) -> Audit | None:
    """Return the audit if it exists AND belongs to ``user_id``, else None.

    Anonymous audits (``user_id IS NULL``) are excluded — they're
    handled by a separate read path that doesn't need owner checking.
    """
    stmt = select(Audit).where(
        Audit.id == audit_id,
        Audit.user_id == _coerce_user_uuid(user_id),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def delete_audit_owned_by(
    session: AsyncSession,
    *,
    audit_id: uuid.UUID,
    user_id: str,
) -> bool:
    """Delete an audit owned by ``user_id``; return True on actual delete.

    A delete that doesn't match a row (wrong owner, already gone)
    returns False — the route layer maps that to 404 so an attacker
    can't enumerate audit ids by probing the delete endpoint either.
    """
    stmt = delete(Audit).where(
        Audit.id == audit_id,
        Audit.user_id == _coerce_user_uuid(user_id),
    )
    # ``execute`` of a DML statement returns a CursorResult; the
    # ``Result[Any]`` umbrella mypy infers doesn't expose rowcount, so
    # the cast keeps the type-check honest about what we know.
    result = cast(CursorResult[Any], await session.execute(stmt))
    await session.commit()
    deleted = (result.rowcount or 0) > 0
    if deleted:
        _log.info("audits.deleted", audit_id=str(audit_id), user_id=user_id)
    return deleted


async def delete_pii_vault_for_user(
    session: AsyncSession,
    *,
    user_id: str,
) -> int:
    """Delete every PII vault row owned by ``user_id``; return the count.

    A user may legitimately hold more than one PII row (e.g. address
    changed and the old vault was retained for in-flight audits). The
    deletion is a sweep: every matching row goes. Audits stay — the
    FK ``SET NULL`` on ``audits.user_pii_vault_id`` fires, leaving
    each audit's anonymized payload intact for the regional aggregate.

    Idempotent: re-calling on a user with no rows returns 0 and
    commits no work.
    """
    stmt = delete(UserPiiVault).where(
        UserPiiVault.user_id == _coerce_user_uuid(user_id),
    )
    result = cast(CursorResult[Any], await session.execute(stmt))
    await session.commit()
    rows = result.rowcount or 0
    if rows:
        _log.info("pii_vault.deleted", user_id=user_id, rows=rows)
    return rows


def _coerce_user_uuid(user_id: str) -> uuid.UUID:
    """``user_id`` is typed as ``str`` at the API layer (Phase 2 will
    keep that — JWT subjects are strings) but the column is UUID. We
    coerce here so the SQL filter compares apples to apples; an invalid
    string (e.g. the ``"anonymous"`` sentinel a stray caller might pass
    after Phase 2 lands) raises ``ValueError`` which the route layer
    surfaces as 401 via :func:`require_authenticated`.
    """
    return uuid.UUID(user_id)


__all__ = [
    "delete_audit_owned_by",
    "delete_pii_vault_for_user",
    "find_audit_owned_by",
]
