# Frontend

Next.js 16 (App Router, React 19) + Tailwind 4. Package manager: **bun**.

## Layout (target — see [`docs/ENGINEERING.md`](../docs/ENGINEERING.md) for full spec)

```
frontend/
  app/               Next.js App Router routes
    (marketing)/landing/
    (app)/wizard/
    (app)/results/
    (app)/audit/                                      [Phase 1b]
    (app)/pricing/
  components/
    ui/              Solstice·Ink primitives          [chart-solar-2hf epic]
    charts/          HeroChart, MonthlyBars, …
    feedback/        ErrorBoundary, Skeleton, ProgressSteps, EmptyState
    forms/           TanStack Form + Zod-bound fields
  lib/
    env.ts           Validated env (NEXT_PUBLIC_* only)
    api/             Generated typed client (OpenAPI → TS)   [Phase 1a]
    queries/         TanStack Query hooks
    intl/            Currency / date / number Intl wrappers
    entitlements/    useEntitlement client hook
    state/           Cross-route stores (wizard, audit)
    theme.ts         Solstice·Ink tokens
```

Hard rules: every server-bound type comes from the generated API client (no hand-rolled types); currency / date formatting goes through `lib/intl/`; long ops show `<Skeleton/>` or `<ProgressSteps/>` (never a blocking spinner); every route has an `<ErrorBoundary/>`.

## Quickstart

```bash
bun install
bun run dev          # http://localhost:3000
bun run lint
bun run typecheck
bun run build
```

The dev server expects the API at `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000` — start the backend with `uv run uvicorn backend.main:app --reload`).

## Configuration

`frontend/lib/env.ts` validates `NEXT_PUBLIC_*` vars and is the only place that should read `process.env`. Backend config (DB / Redis / Stripe / Vertex / S3 / Resend / Auth) lives in [`backend/config.py`](../backend/config.py) — frontend never sees those values.
