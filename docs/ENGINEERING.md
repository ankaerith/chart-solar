# Engineering Practices

Operating manual for humans + agents working on this codebase. Covers what we expect of every change, where things live, and the patterns we keep coming back to.

## Definition of Done

A bead is closed when:

1. **Tests pass.** New behavior has new tests; modified behavior has updated tests. `uv run pytest` and `pnpm test` are green locally and in CI.
2. **Types pass.** `mypy --strict` on backend; `pnpm typecheck` on frontend. No `# type: ignore` without a reason comment.
3. **Lints pass.** `ruff check`, `pnpm lint`, no AGPL/SSPL/Commons Clause in the dep graph.
4. **Acceptance criteria each addressed.** Not "mostly" — each numbered item from the bead's `acceptance_criteria` is true, or a follow-up bead exists for the gap with a link from this PR.
5. **No new ZFC violations.** Application code does not embed semantic logic the model should be doing (per `PRODUCT_PLAN.md` § Cognition Architecture). If a PR introduces one knowingly — flag it in the description.
6. **Snapshot integrity.** Engine changes pin `engine_version` + `pvlib_version`; prompt changes pin `prompt_version`. Saved artifacts re-open without silent recomputation.
7. **License + attribution.** New data source → entry in `/credits`; new dependency → license verified; cached rows carry source attribution columns.
8. **PII boundary respected.** Any read of user-scoped data goes through `require_owner`. Any write of installer-rep data strips direct contact PII at extraction.
9. **Disclaimer present.** AI-assist + not-financial-advice disclaimer appears on every audit report and exported methodology PDF. Non-negotiable.
10. **Manual verification stated.** UI work has been opened in a real browser. API work has a verified curl/test. "Tests pass" is not the same as "feature works."

PR template (`.github/PULL_REQUEST_TEMPLATE.md`) restates this checklist.

## Backend layout

```
backend/
  api/                 # FastAPI routes; thin — orchestration only
    deps.py              # require_owner, get_db, get_user, etc.
    irradiance.py        # GET /api/irradiance
    forecast.py          # POST /api/forecast → enqueue
    forecast_status.py   # GET /api/forecast/{job_id}
    audits.py            # POST /api/audits, GET /api/audits/{id}
    me.py                # DELETE /api/me/data, etc.
  domain/              # pure data models; no IO
    inputs.py            # SystemInputs, FinancialInputs, TariffInputs (Pydantic)
    outputs.py           # ForecastResult, AuditResult
    events.py            # ForecastCompleted, AuditCompleted, PaymentSucceeded
  engine/              # pure functions; no side effects
    pipeline.py          # run_forecast(inputs) → ForecastResult
    steps/               # one module per pipeline step (irradiance, dc_production, finance, …)
    registry.py          # feature-flag-aware step registration
  providers/           # ports + adapters for upstream data
    irradiance/          # NsrdbProvider, PvgisProvider, OpenMeteoProvider
    tariff/              # UrdbProvider, OctopusProvider, ManualProvider
    incentive/           # state credits, rebates, SREC
    geocoding/           # Google Place ID adapter
    monitoring/          # Enphase, SolarEdge, Tesla CSV, GivEnergy
  services/            # use-case orchestration (impure, IO at boundary)
    forecast_service.py  # consumes engine + providers; emits events
    audit_service.py
    entitlements/
      features.py
      guards.py
  workers/             # job queue consumers
    forecast_worker.py
    extraction_worker.py
    ttl_worker.py        # purges raw PDFs after 24-72h
  infra/               # cross-cutting tech utilities
    logging.py           # structured logger + correlation IDs
    tracing.py           # OpenTelemetry setup
    retry.py             # tenacity wrappers
    idempotency.py       # keyed POST + webhook dedupe
    eventbus.py          # in-process pub/sub
  prompts/             # versioned prompt templates
    extraction/v1.txt
  alembic/             # migrations (one per schema delta)
```

**Hard rules**:
- `domain/` and `engine/` import nothing from `api/`, `services/`, `workers/`, `providers/`, `infra/`. Pure-function discipline.
- `providers/` define `Protocol`s in `__init__.py`; adapters live in subpackages. Tests use `FakeProvider` against the same Protocol.
- `services/` is where IO lives. `api/` is glue that calls services and shapes responses.
- Long-running compute is **always** via the queue. Synchronous API endpoints have a 5-second budget.
- New pipeline step: schema → golden fixture → impl → docs → registry entry. See engine-step formula (`bd formula`).

## Frontend layout

```
frontend/
  app/                   # Next.js App Router routes
    (marketing)/landing/
    (app)/wizard/
    (app)/results/
    (app)/audit/
    (app)/pricing/
  components/
    ui/                  # primitives: Btn, Field, SegBtn, ValuesChip, … (Solstice·Ink)
    charts/              # HeroChart, MonthlyBars, BatteryDispatch, TornadoChart
    feedback/            # ErrorBoundary, Skeleton, ProgressSteps, EmptyState
    forms/               # TanStack Form + Zod-bound field components
  lib/
    api/                 # generated typed client (OpenAPI → TS)
    queries/             # TanStack Query hooks
    intl/                # currency/date/number Intl wrappers (£/$ branch on locale)
    entitlements/        # useEntitlement client hook
    state/               # cross-route stores (wizard state, audit state)
    theme.ts             # Solstice·Ink tokens
```

**Hard rules**:
- Every server-bound type comes from the generated `lib/api/` client. No hand-rolled API types.
- Currency/date/number formatting goes through `lib/intl/`. No raw `$`/`£` template literals.
- Form validation is Zod schemas in `lib/api/schemas/` (shared with the OpenAPI client). Server-side Pydantic and client-side Zod are generated from the same source where feasible.
- Long-running operations show a `<Skeleton/>` or `<ProgressSteps/>`; never a blocking spinner.
- Every route is wrapped in an `<ErrorBoundary/>` with a route-appropriate fallback.

## Testing strategy

| Layer | Tool | Goal |
|---|---|---|
| Engine math | pytest + Hypothesis (property-based) | NPV/IRR/amortization invariants |
| Engine pipeline | pytest + golden fixtures | Output stable within tolerance |
| Provider adapters | pytest + recorded fixtures (`vcr.py` or hand-curated JSON) | No live API in CI |
| Service / API | pytest + httpx + test DB | Auth boundary, idempotency, validation |
| Worker | pytest + RQ test mode | Job round-trip |
| Component | Vitest + Testing Library | Component contracts |
| E2E | Playwright | Wizard golden flow, audit golden flow |
| Visual regression | Playwright snapshots | Solstice·Ink doesn't drift |
| Accessibility | axe-core in CI + manual screen-reader pass | WCAG 2.1 AA on Tier 1 routes |
| Synthetic monitor | external golden-flow probe | Black-box health from outside the cluster |

## Environments

- **Local dev**: `docker compose up` boots api+worker+postgres+redis+clamd. External APIs are mocked: a `providers/fake/` ships hand-curated NSRDB / PVGIS / Vertex AI / Stripe fixtures. No internet access required for green tests.
- **CI**: identical compose stack. CI also runs `pip-licenses` (fail on AGPL/SSPL/Commons Clause), `ruff`, `mypy --strict`, `pnpm typecheck`, `pnpm lint`, axe-core, and a 30-second engine performance regression budget.
- **Staging**: identical to prod, fed by a thin slice of synthetic users + fixture proposals.
- **Production**: Fly.io containers; CDN for static; managed Postgres.

## Operational expectations

- Every external call: retry with backoff (`infra/retry.py`); circuit-breaker on third consecutive failure; logged with correlation ID.
- Every POST endpoint that mutates: idempotency key from client OR derived from inputs; second identical call returns the first result.
- Every webhook: signed (`stripe.Webhook.construct_event`), idempotent, logged with the upstream event ID.
- Every long job: enqueued, status pollable, dead-letter after N retries.
- Every secret: in env, never in code; rotation cadence per `chart-solar-7wxq`.

## Architecture decisions

See [docs/adr/](./adr/). Anything that fits the "future reader will be surprised" test gets an ADR.

## Plan documents

- [`VISION.md`](../VISION.md) — strategic north star (wins on conflicts)
- [`PRODUCT_PLAN.md`](../PRODUCT_PLAN.md) — engineering / feature spec
- [`BUSINESS_PLAN.md`](../BUSINESS_PLAN.md) — competitive, pricing, success metrics
- [`LEGAL_CONSIDERATIONS.md`](../LEGAL_CONSIDERATIONS.md) — IP, commercial, AUP, retention
