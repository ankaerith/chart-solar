"""GET / DELETE /api/audits/{id}.

Owner-scoped read + delete. Both endpoints filter by ``user_id`` via the
``audit_service`` helpers; a wrong-owner request returns 404, never 403
(prevents ID enumeration).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

import backend.database as _db
from backend.api.auth import require_authenticated
from backend.infra.logging import get_logger
from backend.services.audit_service import (
    delete_audit_owned_by,
    find_audit_owned_by,
)

router = APIRouter()
_log = get_logger(__name__)


@router.get("/audits/{audit_id}")
async def get_audit(
    audit_id: uuid.UUID,
    user_id: str = Depends(require_authenticated),
) -> dict[str, Any]:
    """Return the audit if owned by the caller; 404 otherwise.

    The owner check happens via the SQL WHERE clause in
    :func:`find_audit_owned_by` — there is no path that loads an audit
    without also filtering by ``user_id``. Anonymous (``user_id IS NULL``)
    audits are deliberately invisible from this route; they're handled
    by their separate by-token surface that does not need ownership.
    """
    async with _db.SessionLocal() as session:
        audit = await find_audit_owned_by(session, audit_id=audit_id, user_id=user_id)
    if audit is None:
        # Wrong-owner OR genuinely-not-found — collapsed to 404 to
        # prevent ID enumeration (chart-solar-kqkr).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {
        "id": str(audit.id),
        "created_at": audit.created_at.isoformat(),
        "location_bucket": audit.location_bucket,
    }


@router.delete("/audits/{audit_id}")
async def delete_audit(
    audit_id: uuid.UUID,
    user_id: str = Depends(require_authenticated),
) -> dict[str, Any]:
    """Hard-delete an audit owned by the caller; 404 otherwise.

    The associated ``installer_quotes`` rows go via FK ``ondelete=CASCADE``;
    the user's PII vault row stays put (FK ``ondelete=SET NULL`` on
    ``audits.user_pii_vault_id``). The raw PDF in object storage is
    purged separately by the TTL job (chart-solar-ebo); this endpoint
    doesn't reach into S3 because the storage adapter isn't a hard
    dependency of the deletion path — losing the row before the PDF is
    purged is fine; the TTL job sweeps orphaned objects regardless.
    """
    async with _db.SessionLocal() as session:
        deleted = await delete_audit_owned_by(session, audit_id=audit_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {"status": "deleted", "audit_id": str(audit_id)}
