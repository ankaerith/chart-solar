from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import audits, entitlements, forecast, health, irradiance, me, stripe_webhook
from backend.api.auth.magic_link import router as auth_router
from backend.api.auth.session_middleware import SessionMiddleware
from backend.config import MissingConfigError, settings
from backend.infra.http import aclose_all_clients
from backend.infra.logging import configure_logging, get_logger
from backend.infra.middleware import BodySizeLimitMiddleware, CorrelationIdMiddleware
from backend.services.entitlements_subscribers import register_subscribers

_log = get_logger(__name__)

configure_logging("api")

#: Default body-size cap (1 MiB). The forecast input (8760 hourly_kwh
#: floats + a small set of scalars) tops out at ~70 KB legitimately;
#: this leaves headroom for future payload growth without exposing the
#: workers to memory-pressure abuse. Per-path overrides below tighten
#: the Stripe webhook further.
_DEFAULT_BODY_MAX_BYTES = 1 * 1024 * 1024
_STRIPE_WEBHOOK_MAX_BYTES = 256 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Register the entitlements grant/revoke handlers on the in-process
    # event bus. Idempotent — safe to re-enter on a hot reload.
    register_subscribers()
    try:
        yield
    finally:
        # Drain the per-service AsyncClient cache so process exit
        # doesn't leak open sockets / connection pools.
        await aclose_all_clients()


app = FastAPI(
    title="Chart Solar API",
    version="0.0.0",
    lifespan=lifespan,
)


@app.exception_handler(MissingConfigError)
async def _missing_config_handler(request: Request, exc: MissingConfigError) -> JSONResponse:
    """Translate a missing-required-secret error into a structured 503.

    Without this handler the route returns plain-text ``Internal Server
    Error`` (HTTP 500) — the frontend can't parse it and the operator
    can't distinguish missing-config from any other unhandled exception.
    503 is the correct semantic: the route would work, but a backing
    secret isn't configured.
    """
    _log.error("config.missing_required", setting=exc.name, path=request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": f"required setting `{exc.name}` is not configured"},
    )


# Order matters: CorrelationId outermost (so every log line carries
# the request id), then BodySizeLimit (reject oversized bodies before
# we touch any DB / signature-verify code), then Session (so every
# route sees the resolved user id on request.state), then CORS.
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    BodySizeLimitMiddleware,
    default_max_bytes=_DEFAULT_BODY_MAX_BYTES,
    per_path_max_bytes=[("/api/stripe/webhook", _STRIPE_WEBHOOK_MAX_BYTES)],
)
app.add_middleware(SessionMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(forecast.router, prefix="/api")
app.include_router(irradiance.router, prefix="/api")
app.include_router(entitlements.router, prefix="/api")
app.include_router(stripe_webhook.router, prefix="/api")
app.include_router(audits.router, prefix="/api")
app.include_router(me.router, prefix="/api")
app.include_router(auth_router, prefix="/api")
