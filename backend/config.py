"""Pydantic Settings — single source of truth for backend env vars.

Fields are flat with feature-prefix conventions (`S3_*`, `VERTEX_*`, `STRIPE_*`)
to match documentation in `.env.example`. Optional fields default to `None`
so the app boots in dev without third-party credentials; consumers fail loudly
when they need a missing value.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Runtime
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Database + queue
    database_url: str = "postgresql+asyncpg://chart_solar:chart_solar@localhost:5432/chart_solar"
    redis_url: str = "redis://localhost:6379/0"

    # Frontend → API
    cors_origins: list[str] = ["http://localhost:3000"]

    # S3-compatible object storage (R2 / S3 / GCS / MinIO) — chart-solar-g93
    s3_bucket: str | None = None
    s3_region: str = "auto"
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    # Vertex AI (PDF extraction — Phase 1b) — chart-solar-5e1
    vertex_project_id: str | None = None
    vertex_location: str = "us-central1"
    vertex_credentials_json: str | None = None

    # Stripe (Decision Pack / Founders / Track) — chart-solar-79i
    stripe_secret_key: str | None = None
    stripe_publishable_key: str | None = None
    stripe_webhook_secret: str | None = None

    # Resend (transactional email — magic links, audit delivery)
    resend_api_key: str | None = None
    resend_from_email: str = "noreply@chartsolar.io"

    # Sentry (error tracking)
    sentry_dsn: str | None = None

    # Auth (FastAPI-native magic-link JWT path)
    auth_jwt_secret: str | None = None
    auth_magic_link_ttl_seconds: int = 900


settings = Settings()


def require(value: str | None, name: str) -> str:
    """Assert a config value is set; raise a clear error if not."""
    if not value:
        raise RuntimeError(f"Required setting `{name}` is not set; check your environment.")
    return value
