"""User-self routes — read + mutate the caller's own data.

Today: ``DELETE /api/me/pii`` (purge PII vault rows) and
``PATCH /api/me/aggregation`` (per-user aggregation opt-out, ADR 0005).
The ``DELETE /api/me/data`` sweep (audits + quotes + saved forecasts +
PII in one call) lands in chart-solar-bf2 once the saved-forecasts
table exists; this module ships the per-resource paths the user
typically reaches for first.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import backend.database as _db
from backend.api.auth import require_authenticated
from backend.infra.logging import get_logger
from backend.services.audit_service import (
    delete_pii_vault_for_user,
    set_user_aggregation_opt_out,
)

router = APIRouter()
_log = get_logger(__name__)


class AggregationOptOutBody(BaseModel):
    """Body for ``PATCH /api/me/aggregation``."""

    opt_out: bool


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


@router.patch("/me/aggregation")
async def patch_my_aggregation(
    body: AggregationOptOutBody,
    user_id: str = Depends(require_authenticated),
) -> dict[str, Any]:
    """Set the caller's aggregation opt-out flag (ADR 0005).

    Cascade + no-auto-resume semantics live in
    :func:`backend.services.audit_service.set_user_aggregation_opt_out`.
    """
    async with _db.SessionLocal() as session:
        result = await set_user_aggregation_opt_out(
            session,
            user_id=user_id,
            opt_out=body.opt_out,
        )
    return {"status": "ok", **result}
