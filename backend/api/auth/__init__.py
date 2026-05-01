"""FastAPI dependencies for the authentication boundary.

:func:`require_authenticated` rejects anonymous callers with HTTP 401.

Owner enforcement happens in SQL: user-scoped queries filter by
``user_id`` in the WHERE clause, so wrong-owner and not-found collapse
to the same "no row" result and the route returns 404 rather than 403
(prevents ID enumeration). See ``docs/ENGINEERING.md`` § DoD #8.
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
