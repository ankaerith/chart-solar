# chart-solar

**Plan it. Check it. Track it.** — the honest math for your roof, before, during, and after.

Independent forecasting, proposal auditing, and post-install variance tracking for residential solar. US + UK at launch.

## Repo status

Phase 0: planning artifacts only. No code yet.

## Planning artifacts

Read in this order:

1. [`VISION.md`](VISION.md) — strategic north star. Problem, product, financial model, positioning, moat. Where this and `PRODUCT_PLAN.md` conflict, this wins.
2. [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md) — engineering / feature spec. Tech stack, modeling architecture, cognition architecture (ZFC), data strategy, MVP scope, Proposal Audit deep-dive, phased roadmap, verification.
3. [`BUSINESS_PLAN.md`](BUSINESS_PLAN.md) — competitive analysis, market sizing, pricing, success metrics, operating costs, business-side risks.
4. [`LEGAL_CONSIDERATIONS.md`](LEGAL_CONSIDERATIONS.md) — data-source IP, commercial-use risk, LLM AUP analysis, retention policy.

## Quickstart

```bash
cp .env.example .env
docker compose up                                       # postgres + redis + api + worker + web
uv sync && uv run uvicorn backend.main:app --reload     # API only, on :8000
cd frontend && bun install && bun run dev               # Web only, on :3000
uv run pytest                                           # Backend tests
```

API at http://localhost:8000/api/health · Web at http://localhost:3000

## Engineering docs

- [`docs/ENGINEERING.md`](docs/ENGINEERING.md) — Definition of Done, repo layout, testing strategy, operational expectations.
- [`docs/adr/`](docs/adr/) — Architecture Decision Records (Phase 1 closed decisions and beyond).
- [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) — PR checklist mirroring DoD.

## Next

Phase 1a: pvlib pipeline, irradiance providers (NSRDB / PVGIS / Open-Meteo), tariff (flat + TOU + NEM 3.0), finance, Monte Carlo. See `PRODUCT_PLAN.md` § Phased Roadmap.

Stack: Next.js 16 (App Router, React 19) + Tailwind 4 frontend, FastAPI + pvlib backend, Postgres + Redis. Frontend uses **bun**; backend uses **uv**. Container-based and portable — deployment target is undecided.
