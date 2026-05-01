"""FastAPI dependencies for the authentication boundary.

:func:`require_authenticated` gates a route on a caller having a real
user id. Today, ``current_user_id`` returns ``"anonymous"``; this dep
refuses anonymous callers with HTTP 401. When magic-link auth lands
(chart-solar-ij9) the dep stays put — only its delegate
``current_user_id`` swaps to the JWT-bound implementation.

Owner enforcement is intentionally **not** a Python-side helper here:
every user-scoped query in ``backend/services/audit_service.py``
(``find_audit_owned_by``, ``delete_audit_owned_by``,
``delete_pii_vault_for_user``) filters by ``user_id`` in the SQL WHERE
clause. There is no load-then-check path, so a wrong-owner request
returns the same "no row" result as a genuinely-missing row — which the
route surfaces as HTTP 404, never 403, to prevent ID enumeration. New
user-scoped resources should follow the same pattern (scope the query,
let "not found" cover both cases).

This module lives under ``backend/api/auth/`` so future auth surface
(login, sign-out, magic-link, JWT helpers) can stack alongside without
forcing ``api/`` itself to grow a flat 20-module file dump.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from backend.entitlements.guards import ANONYMOUS_USER_ID, current_user_id


def require_authenticated(user_id: str = Depends(current_user_id)) -> str:
    """Reject anonymous callers with HTTP 401; return the caller's user id.

    Routes that read or write user-scoped data declare ``user_id =
    Depends(require_authenticated)`` instead of ``current_user_id``;
    once magic-link auth ships the underlying dep returns the JWT
    subject and ``ANONYMOUS_USER_ID`` simply stops appearing.
    """
    if user_id == ANONYMOUS_USER_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
        )
    return user_id


__all__ = ["require_authenticated"]
