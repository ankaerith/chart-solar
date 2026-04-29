# Secrets management

Source of truth: `.env.example`. Every backend env var is mirrored on `backend.config.Settings`; every frontend env var is mirrored on `frontend/lib/env.ts`.

## Local development

```bash
cp .env.example .env
# fill values you need; leave third-party keys blank to disable those features
```

`.env` is gitignored. Never commit real keys.

`backend/config.py` boots with safe defaults, so you can run the engine + tests without configuring Stripe / Vertex / S3 / Resend / Sentry / auth — those features assert their own secrets at the call site.

## Production secrets

We don't ship credentials in container images. Each deploy target reads them from a managed secret store at process startup.

| Target | Mechanism |
|---|---|
| **Fly.io (launch default)** | `fly secrets set KEY=value`; values appear as env vars in the running container. |
| **AWS Fargate / ECS (portability target)** | AWS Secrets Manager → ECS task-definition `secrets:` block → injected as env vars. |
| **Self-hosted (any container host)** | Docker / systemd env files protected at filesystem-permission level; rotated via the host's config-management tool. |

**Required at launch (production):**

- `DATABASE_URL` (managed Postgres connection string)
- `REDIS_URL` (managed Redis or self-hosted)
- `AUTH_JWT_SECRET` (≥ 32 random bytes)
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- `RESEND_API_KEY`
- `SENTRY_DSN`
- `S3_*` (one of R2 / S3 / GCS)

**Required when feature ships (Phase 1b+):**

- `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `VERTEX_CREDENTIALS_JSON`

## Rotation

- **Auth secrets** (`AUTH_JWT_SECRET`): rotate on incident or annually. Rotation invalidates outstanding magic-link tokens — acceptable.
- **Stripe webhook secret**: rotate on incident; coordinate with Stripe dashboard rotation flow.
- **Vertex / S3 credentials**: rotate every 90 days. Use IAM short-lived credentials where the host supports it (workload identity on GCP, IAM roles on AWS).
- **Sentry DSN**: not a secret — DSN is public-by-design — but treat env-specific DSNs as separate values.

## Never

- Never log a secret value (correlation IDs / job IDs / job kwargs are fine; secrets are not).
- Never bake secrets into Docker images. `docker history` exposes them.
- Never commit `.env`, `.env.local`, `.env.production`, `*.pem`, `service-account.json`. `.gitignore` covers the common cases; `gitleaks` (pre-commit) catches the rest.

## Reading values

Backend:

```python
from backend.config import settings, require

key = require(settings.stripe_secret_key, "STRIPE_SECRET_KEY")
```

Frontend:

```typescript
import { env } from "@/lib/env";

fetch(`${env.apiUrl}/api/forecast`, …);
```
