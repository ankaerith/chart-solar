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

    # S3-compatible object storage (R2 / S3 / GCS / MinIO)
    s3_bucket: str | None = None
    s3_region: str = "auto"
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    # Vertex AI (PDF extraction). ZDR is non-negotiable for production —
    # the client wrapper refuses to start unless both flags are true. The
    # abuse-logging exemption requires GCP-side enrollment per
    # ``LEGAL_CONSIDERATIONS.md § G1b``; the flag here only attests that
    # the project-level setting has been requested + granted.
    vertex_project_id: str | None = None
    vertex_location: str = "us-central1"
    vertex_credentials_json: str | None = None
    vertex_zdr_enabled: bool = False
    vertex_abuse_logging_exempt: bool = False

    # Stripe
    stripe_secret_key: str | None = None
    stripe_publishable_key: str | None = None
    stripe_webhook_secret: str | None = None

    # Resend (transactional email)
    resend_api_key: str | None = None
    resend_from_email: str = "noreply@chartsolar.io"

    # Irradiance providers
    nsrdb_api_key: str | None = None
    nsrdb_user_email: str | None = None  # NREL PSM3 requires a registered email
    openmeteo_paid_enabled: bool = False
    openmeteo_paid_api_key: str | None = None

    # URDB (NREL Utility Rate Database) — same NREL developer key works
    # for both NSRDB and URDB, but a dedicated setting keeps the lookup
    # path obvious.
    urdb_api_key: str | None = None

    # Sentry
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
