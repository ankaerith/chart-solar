"""HTTP middleware: correlation IDs + per-route body-size caps.

* :class:`CorrelationIdMiddleware` honors ``X-Request-Id`` from the
  client when present; otherwise mints a fresh uuid4 hex. The value is
  bound to a ContextVar so structlog picks it up automatically in every
  log emitted during the request.
* :class:`BodySizeLimitMiddleware` rejects requests whose
  ``Content-Length`` exceeds a per-path cap before the body is read so
  a malicious client can't push gigabytes into worker memory before
  validation / signature verification runs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.infra.logging import get_logger, new_correlation_id, set_correlation_id

_log = get_logger(__name__)


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


class BodySizeLimitMiddleware:
    """Reject oversized POST/PUT/PATCH bodies before they hit the route.

    Two reasons to enforce in middleware rather than per-route:

    1. Defence in depth — the reverse proxy in front of prod *should*
       cap with ``client_max_body_size`` or equivalent, but the API
       can't depend on that being there in every deploy target.
    2. The Stripe webhook needs the cap to land before signature
       verification reads the body, otherwise an attacker who knows
       the public webhook URL can buffer an arbitrary payload before
       the HMAC check rejects it.

    Per-path caps are passed as a list of ``(prefix, max_bytes)``
    pairs. The longest matching prefix wins so ``/api/forecast`` can
    have a different cap from ``/api/stripe``. Unmatched paths fall
    back to ``default_max_bytes``. Requests whose ``Content-Length``
    is missing or unparseable get the default cap; the default is
    deliberately conservative (1 MiB) — large legitimate uploads
    (proposal PDFs, etc.) belong on dedicated routes that override.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_max_bytes: int,
        per_path_max_bytes: list[tuple[str, int]] | None = None,
    ) -> None:
        self.app = app
        self.default_max_bytes = default_max_bytes
        # Sort longest-prefix-first so we never short-circuit on a less
        # specific match.
        self.per_path = sorted(
            per_path_max_bytes or [], key=lambda pair: len(pair[0]), reverse=True
        )

    def _max_bytes_for(self, path: str) -> int:
        for prefix, cap in self.per_path:
            if path.startswith(prefix):
                return cap
        return self.default_max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in {"POST", "PUT", "PATCH"}:
            await self.app(scope, receive, send)
            return

        cap = self._max_bytes_for(scope.get("path", ""))
        content_length_header: str | None = None
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                content_length_header = value.decode("latin-1")
                break

        if content_length_header is not None:
            try:
                content_length = int(content_length_header)
            except ValueError:
                content_length = None
            if content_length is not None and content_length > cap:
                _log.warning(
                    "middleware.body_too_large",
                    path=scope.get("path"),
                    content_length=content_length,
                    cap=cap,
                )
                response = JSONResponse(
                    {"detail": "request body too large"},
                    status_code=413,
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
