"""User-self routes — read + delete the caller's own data.

Today: just ``DELETE /api/me/pii`` so a signed-in user can purge their
PII vault row independently of any audit. The ``DELETE /api/me/data``
sweep (audits + quotes + saved forecasts + PII in one call) lands in
chart-solar-bf2 once the saved-forecasts table exists; this PR ships
the per-resource path the user typically reaches for first.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

import backend.database as _db
from backend.api.auth import require_authenticated
from backend.infra.logging import get_logger
from backend.services.audit_service import delete_pii_vault_for_user

router = APIRouter()
_log = get_logger(__name__)


@router.delete("/me/pii")
async def delete_my_pii(
    user_id: str = Depends(require_authenticated),
) -> dict[str, Any]:
    """Drop every PII vault row owned by the caller; return the row count.

    Audits referencing the deleted vault row stay alive — the FK
    ``SET NULL`` on ``audits.user_pii_vault_id`` fires so the audit's
    anonymized payload remains useful to the regional aggregate even
    after the user's name / email / address are gone.

    Idempotent: a re-call after the first sweep returns ``rows: 0``.
    """
    async with _db.SessionLocal() as session:
        rows = await delete_pii_vault_for_user(session, user_id=user_id)
    return {"status": "deleted", "rows": rows}
