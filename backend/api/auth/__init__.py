"""FastAPI dependencies for the authentication boundary.

Two primitives, one module:

* :func:`require_authenticated` — gates a route on a caller having a
  real user id. Today, ``current_user_id`` returns ``"anonymous"``;
  this dep refuses anonymous callers with HTTP 401. When magic-link
  auth lands (chart-solar-ij9) the dep stays put — only its delegate
  ``current_user_id`` swaps to the JWT-bound implementation.

* :func:`require_owner` — raises HTTP 404 when the resource's user id
  doesn't match the caller's. The status is 404 *not* 403 by design:
  a 403 leaks the existence of an unowned row, allowing an attacker
  to enumerate ids and learn which ones exist. Per
  ``docs/ENGINEERING.md`` § Definition of Done #8: every read of
  user-scoped data goes through this guard.

These live under ``backend/api/auth/`` so future auth surface (login,
sign-out, magic-link, JWT helpers) can stack alongside without forcing
``api/`` itself to grow a flat 20-module file dump.
"""

from __future__ import annotations

import uuid

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


def require_owner(
    *,
    caller_user_id: str,
    resource_user_id: str | uuid.UUID | None,
) -> None:
    """Raise HTTP 404 if the caller doesn't own ``resource_user_id``.

    Anonymous resources (``resource_user_id is None``) also fail —
    routes load anonymous resources through their own narrower path
    (e.g. an audit-by-id endpoint that scopes the query to the caller's
    user id directly). The 404 collapse prevents ID enumeration: an
    attacker cannot tell "doesn't exist" from "exists but not yours."
    """
    if resource_user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if str(resource_user_id) != caller_user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


__all__ = ["require_authenticated", "require_owner"]
