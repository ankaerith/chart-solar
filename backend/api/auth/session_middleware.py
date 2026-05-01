"""Resolve the session cookie → ``request.state.user_id`` per request.

Runs once per request, before the route handler dispatches. Routes
read the result via :func:`backend.entitlements.guards.current_user_id`,
which inspects ``request.state.user_id`` (defaulting to
``ANONYMOUS_USER_ID`` if absent / invalid).

Implementation is a Starlette middleware (sync ``dispatch``) that
opens its own DB session for the lookup. The cost is one indexed
``SELECT`` on ``sessions`` per request that carries a cookie — the
``token_hash`` is the primary key, so the query is index-only.
Requests without the cookie skip the DB hit entirely.

Failures (DB unreachable, malformed cookie, expired session) all
collapse to "anonymous" — the middleware never raises, so a flaky
auth path can never strand an otherwise-public route.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import backend.database as _db
from backend.config import settings
from backend.entitlements.guards import ANONYMOUS_USER_ID
from backend.infra.logging import get_logger
from backend.services.auth_service import user_id_for_session_token

_log = get_logger(__name__)


class SessionMiddleware(BaseHTTPMiddleware):
    """Stamp ``request.state.user_id`` from the session cookie."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        token = request.cookies.get(settings.auth_session_cookie_name)
        request.state.user_id = ANONYMOUS_USER_ID
        if token and _db.SessionLocal is not None:
            try:
                async with _db.SessionLocal() as session:
                    user_id = await user_id_for_session_token(session, raw_token=token)
            except Exception as exc:  # noqa: BLE001 — never strand a request
                _log.warning("auth.session_lookup_failed", error=repr(exc))
                user_id = None
            if user_id is not None:
                request.state.user_id = str(user_id)

        return await call_next(request)
