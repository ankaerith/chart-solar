from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import audits, entitlements, forecast, health, irradiance, me, stripe_webhook
from backend.api.auth.magic_link import router as auth_router
from backend.api.auth.session_middleware import SessionMiddleware
from backend.config import settings
from backend.infra.logging import configure_logging
from backend.infra.middleware import CorrelationIdMiddleware
from backend.services.entitlements_subscribers import register_subscribers

configure_logging("api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Register the entitlements grant/revoke handlers on the in-process
    # event bus. Idempotent — safe to re-enter on a hot reload.
    register_subscribers()
    yield


app = FastAPI(
    title="Chart Solar API",
    version="0.0.0",
    lifespan=lifespan,
)

# Order matters: CorrelationId outermost (so every log line carries
# the request id), Session next (so every route sees the resolved
# user id on request.state), then CORS.
app.add_middleware(CorrelationIdMiddleware)
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
