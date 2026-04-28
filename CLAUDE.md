# Chart Solar — working notes for Claude

## What this repo is
Independent solar forecasting, proposal auditing, and post-install variance tracking. US + UK at launch.

## Read first
- `VISION.md` — strategic north star. Wins ties.
- `PRODUCT_PLAN.md` — engineering / feature spec. Tech stack, ZFC cognition rules, phased roadmap.
- `BUSINESS_PLAN.md` — pricing, market, competitive frame.
- `LEGAL_CONSIDERATIONS.md` — data-source IP, retention policy, LLM AUP.

## Architecture in one paragraph
FastAPI (Python) backend, Next.js 15 (App Router, React 19) frontend, Postgres for state, Redis + RQ for the forecast queue, pvlib for production physics, Vertex AI Gemini for PDF extraction (Phase 1b). Deployed as containers; specific host is undecided and the stack stays portable — no provider-proprietary features in the hot path.

## Engine layout
`backend/engine/pipeline.py` composes `backend/engine/steps/*.py`. Each step is a pure `(state) -> state` transform that registers itself under a feature key. `backend/engine/registry.py` decides which steps run for a given tier.

## ZFC (Zero-Framework Cognition)
Application code is a thin, deterministic shell. Cognition belongs to models. **Anti-patterns to refuse:**
- Regex / pattern matching of semantic fields (installer names, equipment, $/W).
- Per-installer template fingerprinting in app code.
- Hard-coded flag taxonomies.
- Keyword-based document classification.
- Fallback heuristics that encode domain knowledge.

If you find yourself writing one of these, stop. Use a model with structured output instead, and put the structured-output schema at the IO boundary as a Pydantic / TS type.

Pure math (pvlib, NPV, IRR, amortization, tariff arithmetic) stays deterministic in Python. That's not cognition; that's physics + accounting.

## Stack rules
- No Vercel-specific features (Edge runtime, KV, Blob, ISR-specific semantics, Vercel Cron).
- No Supabase RLS coupling, no Supabase Edge Functions. Postgres via portable SQL only.
- Auth: Auth.js (NextAuth) on Postgres or FastAPI-native magic-link JWT — both portable.
- Object storage: S3-compatible (R2, S3, GCS) — same SDK code.

## Testing
- `uv run pytest` — backend
- `cd frontend && npm run lint && npm run typecheck && npm run build` — frontend

## Phase
We're at the end of Phase 0 (repo + scaffold). Next is Phase 1a: pvlib pipeline, irradiance providers (NSRDB / PVGIS / Open-Meteo), DC production, clipping, soiling, temperature, degradation, tariff (flat + TOU + NEM 3.0), finance, Monte Carlo wrapper, async job queue + worker.
