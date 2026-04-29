"""ASGI middleware that mints (or honors) a correlation ID per request.

Honors `X-Request-Id` from the client when present; otherwise mints a fresh
uuid4 hex. The value is bound to a ContextVar so structlog picks it up
automatically in every log emitted during the request.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend.infra.logging import new_correlation_id, set_correlation_id


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    HEADER = "x-request-id"

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        cid = request.headers.get(self.HEADER) or new_correlation_id()
        set_correlation_id(cid)
        try:
            response = await call_next(request)
        finally:
            set_correlation_id(None)
        response.headers[self.HEADER] = cid
        return response
