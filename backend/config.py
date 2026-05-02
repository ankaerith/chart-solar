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

    # Auth (FastAPI-native magic-link path).
    # ``auth_jwt_secret`` is reserved for a future JWT-based session
    # variant; the default magic-link flow uses a Postgres-backed session
    # token and doesn't need a signing secret.
    auth_jwt_secret: str | None = None
    auth_magic_link_ttl_seconds: int = 900  # 15 min — non-negotiable per chart-solar-ij9
    auth_session_ttl_seconds: int = 60 * 60 * 24 * 30  # 30 days
    auth_session_cookie_name: str = "chart_solar_session"
    auth_session_cookie_secure: bool = True
    # Where the magic-link click lands. Front end captures the ``token``
    # query string and POSTs it back to ``GET /api/auth/callback`` via
    # ``window.location``; the cookie is set on that response.
    auth_callback_url: str = "http://localhost:3000/auth/callback"

    # Number of trusted reverse-proxy hops in front of the API. When 0
    # (default) the rate limiter uses the direct peer address only —
    # ``X-Forwarded-For`` is ignored, since a hostile client cycling
    # XFF values would otherwise bypass per-IP buckets. Set to the
    # actual hop count in production (1 for a single edge proxy, 2 for
    # CDN→LB→app, etc.); the operator must guarantee that the outermost
    # trusted proxy scrubs any client-supplied XFF before appending its
    # own observed source address.
    trust_forwarded_for_hops: int = 0


settings = Settings()


class MissingConfigError(RuntimeError):
    """Raised when a required runtime setting is unset.

    Subclass of :class:`RuntimeError` so existing ``except RuntimeError``
    blocks keep catching it; the FastAPI handler in ``backend.main``
    translates it to a structured 503 instead of letting it escape as
    a plain-text 500.
    """

    def __init__(self, name: str) -> None:
        super().__init__(f"Required setting `{name}` is not set; check your environment.")
        self.name = name


def require(value: str | None, name: str) -> str:
    """Assert a config value is set; raise a clear error if not."""
    if not value:
        raise MissingConfigError(name)
    return value
