# Solar Forecast Product — Product Plan

> **Note on scope**: This document is the engineering / feature spec — the basis for spec-driven development. It covers tech stack, modeling architecture, cognition architecture, data strategy, MVP feature scope, the Proposal Audit deep-dive, phased roadmap, and verification. Business framing — competitive analysis, market sizing, pricing, success metrics, team, business-side risks — lives in `BUSINESS_PLAN.md`. Legal and IP risk lives in `LEGAL_CONSIDERATIONS.md`. Strategic north star is `VISION.md`; where this plan and VISION.md conflict, VISION.md wins.

## Phase 1 closed decisions

These four were resolved during the legal review. They are anchors for downstream feature design and architecture, not open questions.

| # | Decision | Implication |
|---|---|---|
| 1 | **PDF retention: extract-and-delete** within 24-72h | `installer_quotes` keeps SHA-256 hash + extracted JSON + audit output. Raw PDF in object storage is auto-purged by a TTL job. Closes the top legal risk (Section F1) and bounds breach radius. |
| 2 | **Aggregation default ON, no Phase 1 UI, opt-out plumbing in place** (revised — see [ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md), supersedes [ADR 0002](docs/adr/0002-aggregation-default-off.md)) | New audits write `aggregation_opt_in=true` on insert; no consent prompt or toggle in Phase 1 UI. `users.aggregation_opt_out` column + `PATCH /api/me/aggregation` endpoint land from day 1 so a future settings page can surface the control without schema work; flipping cascades to mark all the user's existing `installer_quotes.aggregation_opt_in=false`. Lawful basis pivots from Art. 6(1)(a) consent → Art. 6(1)(f) legitimate interests; anonymization (ZIP-3 / postcode-district bucket only, no homeowner identifiers, rep direct contact PII stripped, k-anonymity gate at publish) is load-bearing. UK Phase 3b revisits the default before launch. |
| 3 | **LLM vendor: Vertex AI Gemini, single-vendor at start** | Gemini 2.5 Flash on Vertex AI as primary extractor with ZDR configured. Claude fallback router deferred (re-introduce if extraction quality plateau or vendor outage exposure justifies). Single DPA, single ZDR posture, simpler ops. |
| 4 | **E&O insurance: deferred at Phase 1 launch** | Not bound for MVP audits. Calendar trigger to bind a policy: before Phase 5 public-launch push, or at 50 paid audits/month, whichever first. AI-assistance + not-financial-advice disclaimer on every audit report from day 1 (independent of insurance status). |

## Geographic Scope (Launch)

**US + UK only at launch.** CA + EU phase 2.

| Layer | US | UK |
|---|---|---|
| Irradiance | NREL PVWatts v8 + NSRDB | PVGIS (free, no key) |
| Tariffs | NREL URDB (free) + manual entry | Octopus Energy API (free) + manual SEG entry |
| Incentives | DSIRE-seeded + manual curated DB (license review pending; phase in during Decision Pack depth) | SEG manual curation |
| Weather | Open-Meteo + NOAA | Open-Meteo + Met Office |
| Roof | **Manual tilt/azimuth/shading** (Google Solar API dropped — ToS + per-call cost) | Same |
| Panel/battery specs | Extract from proposal only at launch; equipment DB deferred | Same |

Currency, units, tariff structure, and incentive framework are abstracted from day 1 so adding CA/EU is a data-layer task, not an engine rewrite.

### UK-specific launch-day must-haves (from research)

These are table-stakes for UK credibility; all sit in the data + tariff layer, not the engine core:

1. **PVGIS irradiance backend** (free, no key, UK postcode-level accuracy)
2. **SEG export-rate picker** across top suppliers (Octopus Outgoing ~15p, Octopus Agile Outgoing variable, E.ON Next Export Exclusive ~16.5p, OVO Smart Export ~15p, Scottish Power SmartGen ~12p, British Gas Flex ~6.4p, EDF ~5.6p, Good Energy ~3-5p — rates to verify at launch)
3. **Octopus Agile + Agile Outgoing half-hourly simulator** — 12-month backtest with battery dispatch
4. **Import tariff picker** — Agile, Tracker, Go, Cosy, Intelligent Octopus, plus Ofgem price cap fallback
5. **MCS toggle** — disclose the Microgeneration Certification Scheme (MCS) premium (£500-£1,500) vs. Smart Export Guarantee (SEG) opportunity cost for non-MCS installs
6. **VAT 0% countdown** — flag 31 Mar 2027 sunset in payback math
7. **Green mortgage uplift** — optional Nationwide / NatWest / Barclays rate discount in financing view
8. **£/kWp + £/kWh benchmarks** — UK median ~£1,400-£1,800/kWp installed; show where user's quote sits
9. **Half-hourly smart-meter requirement** — warn users without one that SEG income is blocked
10. **Plain-English verdict** — "Worth it?" headline alongside NPV (addresses recurring MSE/Reddit frustration)
11. **Currency + units** — £, kWh, kWp; never $ or kBTU in UK mode

### US-specific launch-day must-haves

1. **NEM 3.0 (Net Billing Tariff) modeled correctly** (CA post-April 2023: hourly export credits pulled from CPUC Avoided Cost Calculator; battery arbitrage is now ~mandatory for sub-10-yr payback)
2. **State credits, utility rebates, and SRECs** (NY, MA, CO, OR, NJ, MD, PA, DC, OH — expand by audit volume). With no federal residential credit available, state and local incentives now carry disproportionate weight. Model treats every incentive as date-parameterized and jurisdiction-scoped, never hard-coded.
3. **TOU tariff library** for PG&E, SCE, SDG&E, PSE, Xcel, FPL, Duke, APS, SRP, ConEd (expand over time; NREL's URDB is the seed but is stale by weeks)
4. **Loan products** — common solar loan terms (10/15/20/25 yr, dealer-fee modeling; dealer fees of 15-30% on "0% APR" loans are the single most-obscured cost in residential solar — auditing these is high signal)
5. **Solar Renewable Energy Credit (SREC) markets** — NJ, MA, MD, PA, DC, OH where applicable

## Tech Stack

Principle: maximally portable, no provider-proprietary features in the hot path. Moving between container hosts (Fly.io, AWS Fargate/ECS, Railway, Render, self-hosted) is ops work, not code work.

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Next.js 15 (App Router) + TypeScript**, deployed as a **Node.js container** (no Vercel-specific features) | One framework, one mental model. SSG for marketing, client components for `/app/*`. Container deploys to Fly, Fargate, anywhere |
| Backend API | **FastAPI (Python)** in a container | Shares language with the modeling engine. Async. Pydantic schemas generate a typed OpenAPI client for the frontend |
| Compute workers | **Python, same codebase as the API**, separate worker entrypoint | Hourly 8760 simulation, Monte Carlo, pvlib-based production modeling. Runs as a worker process consuming from a queue. No cross-language boundary |
| Calc engine | **pvlib-python from day 1** (`backend/engine/`). Hourly 8760 simulation + Monte Carlo are core, not deferred. Irradiance from NREL PSM3 (US) / PVGIS (UK/EU) / Open-Meteo (global fallback), cached per-bucket in Postgres | NREL-grade physics at launch matches the "we did the hard math" positioning. No TypeScript port + later swap — one engine, one language |
| Queue | **Redis + RQ or Dramatiq** | Portable; swap to SQS on AWS via one adapter class when relevant |
| DB | **Postgres** — self-hosted on Fly, or managed (Fly Postgres, Neon, RDS, Supabase Postgres using portable features only: no Supabase RLS-coupling, no Supabase Edge Functions) | Standard SQL. Migrates across providers with `pg_dump`/`pg_restore` |
| Object storage | **S3-compatible** (R2, S3, or GCS). Same SDK code | PDF uploads (24-72h TTL — see Phase 1 closed decisions), methodology exports, cached irradiance snapshots |
| Auth | **Auth.js (NextAuth) backed by Postgres**, or **FastAPI-native JWT + email magic-links** | Both are portable. Not committing to Clerk, Supabase Auth, or any vendor-locked identity service |
| Payments | **Stripe** | No real alternative for indie SaaS; standard integration |
| Charts | **Recharts** (port pattern from current repo) | Proven. Custom-compose Monte Carlo fan charts (Area + ReferenceLine) |
| UI | **shadcn/ui + Tailwind 4** | Port components from current repo |
| Data fetching (client) | **TanStack Query** + TanStack Router + TanStack Table + TanStack Form + TanStack Virtual | Port patterns from current repo |
| Email | **Resend** free tier (3k/mo); portable path to SES/Postmark | No vendor lock; standard SMTP relay available as fallback |
| Analytics | **Plausible** (self-hostable) or **PostHog** (self-hostable) | No tracking-pixel ad-tech. Brand-consistent with no-lead-gen ethos |
| Error tracking | **Sentry** free tier | Standard |
| LLM (PDF extraction) | **Vertex AI Gemini** (single-vendor at start, per Phase 1 closed decisions). Region `europe-west2` (UK), `us-central1`/`us-east4` (US). ZDR configured. PDFs sent `inline_data` <20 MB. | See Cognition Architecture |
| Hosting (launch) | **Fly.io containers** for API + workers + Postgres. CDN for static Next.js build output | Pay-per-second, scale-to-zero via Machines, generous dev tier, Postgres first-class |
| Hosting (later) | **AWS Fargate/ECS** or any container host | Drop-in; same Dockerfile. Only changes are infra config (Terraform/CDK) |

Operating cost projections live in `BUSINESS_PLAN.md` (Operating Costs section).

## Architecture: Extensible Modeling Engine

Many small modeling refinements are coming (soiling, snow loss, shading factors, bifacial gain, etc.). Engine is a pipeline of composable, individually testable transforms — **pure-Python from day 1, pvlib-backed**. Per ADR 0006, engine steps wrap pvlib for any modeling pvlib supports rather than reimplementing physics — cell-temperature derating and inverter clipping live inside `dc_production`'s ModelChain, not as separate steps.

```
backend/
  engine/
    inputs.py             # Pydantic schemas for SystemInputs, FinancialInputs, TariffInputs
    pipeline.py           # run_forecast(inputs, *, tmy) -> ForecastResult
    steps/
      irradiance.py       # NSRDB / PVGIS / Open-Meteo source adapters (IrradianceProvider)
      dc_production.py    # pvlib ModelChain.with_pvwatts: irradiance + cell-temp + inverter clipping
      soiling.py          # wraps pvlib.soiling once monthly precipitation routes through TmyData
      snow.py             # wraps pvlib.snow once monthly snowfall + RH route through TmyData
      degradation.py      # year-over-year degradation curve (no pvlib equivalent)
      consumption.py      # baseline + EV + heat pump load profiles (ResStock archetypes)
      battery_dispatch.py # 8760-hour TOU dispatch (rule-based at launch; LP-optimized later)
      tariff.py           # flat + tiered + simple-TOU billing
      export_credit.py    # NEM 1:1 + NEM 3.0 NBT + UK SEG (flat / TOU)
      finance.py          # loans, state+local credits, NPV/IRR/payback (orchestrator pending)
      monte_carlo.py      # stochastic wrapper: rate-escalation path × weather year × degradation × hold duration
    finance/              # pure-math primitives: amortization, cashflow (NPV/IRR/MIRR/LCOE)
    registry.py           # feature-flag-aware step registration (engine.<step> keys)
  entitlements/
    features.py           # registry of feature keys → tier
    guards.py             # FastAPI dependency for tier gating
frontend/
  lib/entitlements/
    useEntitlement.ts     # client hook (mirrors server registry)
```

Each step:
- Pure-math entry point — no IO inside the engine; weather is fetched by the worker and passed in
- Has its own unit tests + golden fixtures (cross-validated against the current single-user repo's outputs)
- Registers a flat `engine.<step>` feature key (e.g. `engine.tariff`, `engine.export_credit`) so it can be promoted/demoted between tiers from a config file
- Exposes its assumptions for the "show your work" methodology view

**Snapshots are versioned.** Every saved forecast or audit records the engine version + pvlib version + irradiance-source snapshot. Re-opening a saved audit never silently re-computes with a newer engine; users trust the number because it's reproducible.

**Battery model: 8760-hour dispatch simulation** (per user choice). Inputs: capacity kWh, usable %, round-trip efficiency, max C-rate, reserve %, dispatch strategy (self-consumption / TOU arbitrage / backup). Output: hourly battery SOC, grid import/export, savings vs no-battery baseline.

**Engine provider interface**: the only adapter worth abstracting is the `IrradianceProvider` — the upstream data source for hourly GHI/DNI/DHI + ambient temperature + wind speed. Implementations: `NsrdbProvider` (NREL PSM3 for US), `PvgisProvider` (UK/EU), `OpenMeteoProvider` (global fallback). pvlib itself is not behind an adapter — it's the engine core.

**Snapshot everything anyway.** Even without an engine-backend swap, pvlib versions evolve, irradiance source updates, and tariff data changes. Every saved forecast records engine version + pvlib version + irradiance-source version + tariff-table hash. Re-opening a saved audit never silently re-computes. Users trust the number precisely because it's reproducible.

## Cognition Architecture (ZFC)

Reference: [Zero-Framework Cognition — Steve Yegge](https://steve-yegge.medium.com/zero-framework-cognition-a-way-to-build-resilient-ai-applications-56b090ed3e69).

### Principle

Application code is a **thin, safe, deterministic shell** that does pure orchestration. All cognitive work — semantic extraction, flag generation, ranking, question generation, "does this field value make sense in context" — is delegated to models. Pure math (pvlib physics, NPV, amortization, tariff arithmetic) stays deterministic in Python.

### Cognitive pyramid

Tasks route to the smallest model that can handle them. Phase 1 launch uses Gemini single-vendor on Vertex AI; the pyramid maps onto Gemini's tier ladder:

- **Gemini 2.5 Flash** (default tier) — first-pass extraction on clean digital proposals; simple classification tasks; cheap per-field sanity checks.
- **Gemini 3 Flash** (escalation tier) — ambiguous layouts, contradictory line items, audit-flag generation, ask-your-installer question composition, cross-bid comparison.
- **Gemini 3 Pro** (top tier) — adversarial or unusual documents (handwritten addenda, scanned PDFs, multi-vendor staples), complex multi-bid reasoning, exceptions the escalation tier flags as over its head.

Default is 2.5 Flash; escalation is explicit and deterministic (see below). The pyramid is vendor-shaped but not vendor-coupled — if Claude is reintroduced for redundancy or extraction-quality reasons later, the same tier mapping applies (Haiku → Sonnet → Opus).

### Anti-patterns we explicitly avoid

- Regex or pattern-matching extraction of semantic fields (installer names, equipment models, $/W).
- Per-installer template fingerprinting in application code. We use server-side prompt caching (Vertex AI context caching) instead for economics.
- Hard-coded flag taxonomies ("if DC:AC > 1.35 emit warning FLAG_27"). Flags are model-generated with rationale grounded in our deterministic counterfactual.
- Keyword-based classification of documents into "type" buckets.
- Fallback heuristics that encode domain knowledge ("if panel warranty ≥ 25 yr and microinverter ≥ 20 yr, mark as 'standard-tier'").

Flagging convention: any future contributor who adds code of this shape writes "ZFC violation" in the PR description so it's easy to spot and review.

### What is OK (not cognition, not a framework)

- Pydantic/JSON schemas at the tool-use boundary (IO contracts).
- Deterministic numeric code (pvlib, NPV, IRR, amortization, Monte Carlo sampling).
- File-format guards informing the model (is this a PDF, how many pages, is it password-protected, is it scan-vs-digital) — these are signals, not decisions.
- Light type + range validators on extracted fields (e.g., "kW is numeric, 0.5–50 for residential") that trigger model re-asking, not rule-based correction.
- Model-response caching, retries, queueing, observability, cost tracking.

### Escalation policy — hybrid (deterministic floor + model opinion)

This is the most consequential design choice and the one we're least willing to fully ZFC. Two patterns we considered:

**Pattern A — Pure model self-determination**. The orchestrator trusts the model's self-declared confidence and "needs stronger model" flag to decide escalation. Pros: maximally resilient to edge cases we haven't anticipated. Cons: models can be overconfident or overcautious; cost drift is hard to bound; silent failure modes when the model confidently misextracts.

**Pattern B — Hybrid: deterministic floor + model opinion (recommended at launch)**. A small set of deterministic triggers force escalation independent of the model's opinion:

- File size > threshold → escalation tier
- Page count > threshold → escalation tier
- Scanned-not-OCRd (image-only PDF) → escalation tier with vision
- Password-protected / XFA / malformed PDF → top tier
- Stapled multi-bid (detected by bookmark/outline structure) → escalation tier, one pass per bid
- Any critical-field (gross price, kW-DC, panel count, year-1 kWh claim) with model-declared confidence below a tunable per-field floor → escalate one tier, then user hand-off if still low

Model opinion overlays on this: 2.5 Flash declaring "I'm confident, no escalation needed" is honored unless a deterministic trigger fires; 2.5 Flash declaring "I'm uncertain" escalates even if no deterministic trigger fires. The deterministic floor caps worst-case cost per audit and gives us predictable per-audit spend; the model opinion captures the weird-but-not-obvious cases.

**Pattern C — Fully deterministic routing (rejected)**. Application code classifies documents (regex for installer name, template fingerprint) and picks model based on classification. Most brittle; classic ZFC violation; breaks when installer templates drift.

**Phased approach**:
- **Launch**: Pattern B. Predictable cost, bounded failure modes, explainable behavior.
- **After ~1,000 real audits**: measure correlation between model-declared confidence and actual extraction accuracy on our held-out labeled set. If the model's self-assessment is well-calibrated, soften the deterministic floor and lean more on model opinion (move toward Pattern A). If it isn't, tighten the floor and keep it.

## Weather & Irradiance Data Strategy

Worth making explicit because it's architecturally central and often confused: **pvlib is a modeling library, not a data source.** It consumes weather/irradiance data and runs the physics. So swapping to pvlib changes *how* we model production; it doesn't free us from needing someone's weather data.

### The three layers

1. **Physics/math layer** — pvlib (Python). Stateless, runs anywhere, ~zero hosting cost. Fully local, no external calls required.
2. **Irradiance layer** — hourly GHI/DNI/DHI + ambient temperature + wind speed for the user's lat/lon. This is the data layer that has to come from somewhere.
3. **Financial / tariff layer** — our own curated DB.

### Source options for the irradiance layer

| Source | Coverage | Resolution | Years | Cost | Notes |
|---|---|---|---|---|---|
| **NREL PVWatts v8 API** | US + partial Americas, Asia | ~4km (NSRDB-backed) | TMY + recent | Free, rate-limited | Phase 1 default for US. Whole-package: irradiance + production in one call |
| **NREL NSRDB (PSM3 hourly)** | US + Mexico + Canada border + Caribbean (~−20° to +60° lat, −180° to −20° lon) | ~4km | 1998-present, hourly | Free, rate-limited; dataset bulk download ~4TB full, ~hundreds of GB per variable | Used via pvlib's `iotools.get_psm3()` |
| **PVGIS (JRC)** | EU + Africa + most of Asia + parts of Americas | ~5km | SARAH2 / SARAH3 satellite, TMY + hourly 2005-2020 | Free, no key, no rate limit | Phase 1 default for UK/EU. Global partial coverage |
| **ERA5 / ERA5-Land** (ECMWF) | **Global, every lat/lon on Earth** | 31km / 9km | 1940-present, hourly | Free via Copernicus CDS; bulk data is large but can be subset | True global fallback when other sources don't cover |
| **Open-Meteo** | **Global** | ~11km (aggregates ERA5 + GFS + ECMWF) | Historical + forecast | Free for non-commercial; **paid Standard tier (~€29/mo) required once first paying customer onboards** | Easiest global default — Phase 1 fallback. Free tier license non-commercial; budget the paid tier into Phase 1b if Open-Meteo is in the provider chain at launch |
| **CAMS Solar Radiation** (ECMWF) | Europe + Africa + Middle East + S. Atlantic | ~4km | 2004-present | Free with registration | Higher-fidelity alternative to ERA5 for those regions |
| **Solcast** | Global | 1-2km, forecast + historical | Forecast + TMY | Commercial (~$0.50-2/user/mo at scale) | For Track — forecast-grade data for variance alerts |
| **Meteonorm** | Global | Typical meteorological year | Curated | Commercial license | Nice-to-have; not needed to launch |

  - **launch:** pvlib in the backend calls free public APIs (NREL PSM3 for US, PVGIS for EU, Open-Meteo paid Standard tier global fallback). Cache the 8760-hour TMY per unique lat/lon bucket (1 km grid) in Postgres. After the first few months of traffic, most queries hit cache and we rarely call upstream.
- **Annual irradiance + weather patterns?** Yes — TMY (typical meteorological year) is the standard artifact, 8760 hours representing long-term climatology for a location. PVGIS, NSRDB, and pvlib itself all produce TMY. We cache these per-location and reuse across users and scenarios.

### Implementation sketch

pvlib is in the primary Python backend from day 1 — not a sidecar.

```
backend/
  api/                        # FastAPI routes
    irradiance.py             # GET /api/irradiance?lat=&lon=&source=auto
                              # → returns 8760-hour TMY as JSON
                              # → source=auto routes: US → NREL PSM3, EU → PVGIS, else → Open-Meteo
                              # → cached in Postgres keyed by rounded lat/lon (4 decimal ≈ 11m)
    forecast.py               # POST /api/forecast → enqueues job, returns job_id
    forecast_status.py        # GET /api/forecast/{job_id} → returns status + result when ready
  engine/                     # (as above)
  workers/
    forecast_worker.py        # Dramatiq/RQ worker consuming forecast jobs, runs engine.pipeline.run_forecast
```

Forecast compute (hourly 8760 × Monte Carlo N runs) is too long for a synchronous HTTP request. Pattern:
1. Frontend POSTs inputs → backend enqueues a job → returns `job_id`
2. Frontend polls or subscribes via websocket for completion
3. Worker runs the engine, writes result to Postgres, optionally to object storage for large artifacts
4. Frontend retrieves the result and renders charts

This pattern runs identically on Fly.io, Fargate, or any container host. No provider-specific queue or function runtime.

## MVP Feature Scope (Planner)

1. **Proposal Audit (HERO FEATURE — Decision Pack only)** — the primary entry point to the product. Full deep-dive in next section. Drives the landing page, launch narrative, and data moat. Shipped in Phase 1.
2. **Smart wizard, depth on demand** (alternative entry path for users without a proposal yet)
   - Step 1: Address (geocode → lat/lon, country)
   - Step 2: Utility bill (manual kWh + $/mo, or upload PDF — defer parsing to v1.1)
   - Step 3: System size (auto-suggest from bill; manual override)
   - Step 4: Battery (optional)
   - Step 5: Financing (cash / loan with terms / PPA / UK subscription)
   - Step 6: Results — 25-year forecast with payback, NPV, IRR, monthly cash flow chart, plain-English "Worth it?" verdict
   - "Edit assumptions" button on results opens advanced mode (every input editable + show source)
3. **Scenario engine** (Decision Pack): clone scenario, side-by-side diff, version history
4. **Inverter clipping** (Decision Pack): DC:AC ratio modeling with curve viz
5. **Hourly battery dispatch** (Decision Pack): 8760-hour simulation with TOU arbitrage, NEM 3.0 / Agile Outgoing aware
6. **TOU + export tariff modeling** (Decision Pack): US TOU library + UK Agile half-hourly
7. **Incentives engine** (US state credits / SRECs / utility rebates, UK SEG + VAT 0% cliff + green mortgages) — DSIRE integration deferred until Decision Pack depth phase pending CC-BY-SA review (see LEGAL_CONSIDERATIONS.md Section A)
8. **Regional pricing benchmarks** (public, all tiers) — "Median $/W in your ZIP: $3.41" powered by the audit DB. Free users get benchmarks; Decision Pack gets the full audit. Aggregation is default-ON with no Phase 1 UI surface (per [ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md)); opt-out plumbing exists in API + data model from day 1. K-anonymity gate (chart-solar-5ww) gates publishing.
9. **Methodology export** (PDF showing every assumption + source)
10. **Anonymous → save flow** (results persist in localStorage; sign-up migrates to Postgres)

Explicitly out of MVP: multi-property, EV/heat-pump load modeling (defaults only), Google Solar API, AI conversational wizard, named installer leaderboards (post-launch, when data volume justifies), LP-optimized battery dispatch (rule-based at launch), independence-axis modeling.

## Proposal Audit — Deep Dive (Phase 1 hero feature)

**Why this is the primary Phase 1 feature:**
- It's the most visceral wedge: a homeowner with a $25k quote in hand has immediate, acute need. Conversion intent from that state dwarfs generic "help me think about solar."
- It's the most viral: users screenshot / share "my installer said 14,000 kWh, this tool said 11,200 — saved me $8k" testimonials.
- It's the most defensible: the regional quote DB compounds from day 1 (default-ON aggregation per [ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md)) and a late-comer cannot retroactively catch up to historical quote volume. This is the product's long-term moat.
- It's SEO gold: per-ZIP / per-postcode / per-installer pages backed by real data (once N is sufficient), drawing high-intent searches.
- It integrates the rest of the product naturally: a user who just got their proposal audited is perfectly primed to buy Decision Pack ($79) to run their own scenarios, and to subscribe to Tracker ($9/mo) post-install to verify delivery.

**User flow:**

```
1. Landing page: "Upload your solar quote. We'll audit it against NREL physics, regional pricing, and real-world production data. $79 one-time unlocks Decision Pack."
2. Teaser: pre-generated sample audit walkthrough to build trust pre-purchase
3. Purchase Decision Pack → drag-drop PDF(s) (one or many bids)
4. Extraction pipeline (Gemini 2.5 Flash on Vertex AI → structured JSON via tool-use schema, with confidence scores; PDFs sent inline_data <20MB; ZDR configured)
5. Review screen: user confirms/corrects extracted fields (human-in-the-loop)
6. Back-test: run our engine on each extracted system for user's location
7. Per-bid Variance Report + (if multiple) Cross-bid Comparison Table
8. BOM alternative suggestions (Phase 1 = heuristic rules: flag aggressive DC:AC ratio, oversized battery for TOU profile, short panel warranty, outlier adder pricing; deeper spec-level alternatives defer to a future Equipment DB)
9. Ask-your-installer question list, non-accusatory, sourced
10. No Phase 1 UI prompt. Aggregation contribution is default-ON (per [ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md)); the privacy policy is the single source of truth on this from launch. Future opt-out toggle lands in /settings as a follow-up; the API + data-model plumbing is already in place.
11. Save audit to account; revisit anytime
12. Raw PDF auto-purged within 24-72h (TTL job); extracted JSON + audit output persist
```

### Extraction field inventory (v1 target — to be iterated on real Puget Sound proposals)

Every field is extracted with a confidence score. Low-confidence fields surface to user for correction.

**System / equipment** (extract only what the proposal states; no equipment-DB back-fill at launch):
- Panel: manufacturer, model #, rated watts (STC), warranty claim (if stated)
- Panel count, total DC kW, total AC kW
- Inverter: make, model, type (string/microinverter/hybrid), rated kW; DC:AC ratio computed from extracted values
- Optimizers / rapid shutdown (SolarEdge, Tigo, etc.) if present
- Battery: make, model, usable kWh (or nameplate if only nameplate), backup capability claim
- Mounting: roof / ground, tilt/azimuth if stated
- Monitoring platform & years included

**Financial**:
- Gross system price, $/W or £/W
- Line items / adders: MPU upgrade, trenching, critter guards, decommissioning bond, re-roof, tree trim, permit/interconnect fees, sales tax
- Incentives claimed on the proposal: state credits, utility rebates, SREC pre-sale, SEG (UK). Any claim of a federal residential credit on a post-2025 owned system is captured as-stated (installer may still list it); whether it's actually available is handled by the incentives-engine's date-parameterized ruleset.
- Net price after incentives
- Financing: cash / loan (term, APR, dealer fee, payment), PPA (escalator, buyout), lease, subscription
- Escalator assumed in 20-yr savings projection
- Degradation assumed in projection
- Year-1 production claim (kWh)
- 20-yr or 25-yr savings claim
- Payback year claimed

**Installer / business** (note: rep direct PII — phone/email — is stripped at extraction per LEGAL_CONSIDERATIONS.md F1; only company name + license # retained):
- Company name, license #, address, phone, rep name
- Quote date, expiration
- NABCEP certification claim
- Installation timeline claimed
- Warranty on workmanship (years)

**Operational**:
- Shading assumption or shading study provided
- Production estimate source disclosed (PVWatts / Aurora / installer-proprietary / etc.)
- Monitoring included (how many years free)
- Service agreement terms

### Multi-bid comparison (a headline feature when user has >1 quote)

Single audit is the atomic unit; comparing multiple audits from the same user against each other + our model is the power move:
- Side-by-side table of all bids: $/W, system size, equipment tier, warranty, financing terms, year-1 claim, 20-yr claim
- Our normalized forecast for each (using same location + tariff assumptions)
- Column highlighting outliers (most expensive, weakest warranty, highest escalator assumption)
- "Best value" recommendation with explicit trade-offs (lowest $/W but 12-yr panel warranty vs. 8% premium for Tier-1 25-yr warranty)
- One Ask-your-installer list per bid, tailored to that bid's specific gaps

EnergySage claims to do this. It doesn't — it collects bids and lets you eyeball them. Actually auditing each one and normalizing assumptions is the differentiator.

**Extraction engine (Phase 1 MVP) — ZFC-compliant, tiered routing:**

- **Structured output boundary**: Gemini → JSON via tool-use schema (Pydantic-typed). The schema is an IO contract, not cognition; ZFC-compliant.
- **Tiered model routing (cognitive pyramid)** on Vertex AI Gemini single-vendor (per Phase 1 closed decisions):
  - **Gemini 2.5 Flash** handles the common case: extract fields from clean, digital proposals at low cost (~$0.005 per 10-page audit).
  - **Gemini 3 Flash** handles ambiguous layouts, contradictory line items, atypical templates.
  - **Gemini 3 Pro** handles the long tail: handwritten addenda, scanned-not-OCRd PDFs, multi-vendor stapled uploads, adversarial content.
- **Confidence per field**: the model produces a self-assessed confidence per extracted field plus an overall "needs stronger model?" signal.
- **Escalation policy — hybrid (deterministic floor + model opinion)**. See "Cognition Architecture" section. Short version: deterministic triggers (file size, page count, scan-vs-digital, password-protected, file-format heuristics) can route directly to the escalation tiers. Model-declared low confidence on critical fields also escalates. We do not let the model alone decide escalation at launch; the deterministic floor caps worst-case cost and gives us predictable spend per audit.
- **User hand-off**: if post-escalation confidence is still below the critical-field bar, surface the specific fields to the user for correction before producing the variance report. Never silently emit a bad audit.
- **Prompt caching, not template caching**: we use Vertex AI's context caching to get the cost benefit of stable prompt prefixes without building an installer-template fingerprint dictionary in our application code (that would be a ZFC violation and template-drift trap).
- **BOM "alternative" generation is model work, not rules**: the audit engine produces flags and ask-your-installer questions by giving the model the extracted values, our deterministic counterfactual forecast, regional benchmarks, tariff context, and the user's values weights — then asks for ranked flags with rationale. No hard-coded flag taxonomy in application code.
- **Vertex AI hardening**: PDFs sent `inline_data` <20 MB to avoid the Files API 48h mandatory retention floor. ZDR enabled (context caching disabled, abuse-logging exception requested). Region pinned: `europe-west2` for UK traffic, `us-central1`/`us-east4` for US traffic. AI Studio surface never used in production.

### Privacy architecture — users anonymized, installers retained (internal only)

Asymmetric by design:
- **Users are retained as anonymously as possible.** No customer name, no street address, no signature, no phone, no email on the quote record itself. We keep only what's needed for forecasting (location to a coarse bucket — ZIP-3 in US, postcode district in UK — and the system config the installer quoted). User→quote linkage lives in a separate table keyed by `user_id`, not denormalized onto the quote record. Users can delete their audit (and cascade the PII + raw PDF) at any time.
- **Raw PDF retention: extract-and-delete (24-72h TTL)** per Phase 1 closed decisions. After extraction, the PDF is purged from object storage by a TTL job; we keep SHA-256 hash + extracted JSON + audit output. Users can also explicitly delete extracted records.
- **Installers are retained in full detail**, because that's the point of the DB. Name, license #, physical address, contact info. Sales-rep direct contact PII (phone, email) is stripped at extraction per LEGAL_CONSIDERATIONS.md F1; only rep name + company-level data retained. Stored internally. **NOT exposed publicly at launch** — no leaderboards, no named comparisons, no "Installer X overstates by 14%" pages. Eventually used to drive aggregate region/ZIP trends, and much later (post-legal-review, post-threshold) for transparency disclosures, but default is "we know, we don't say."
- **Regional aggregates (no installer names)** are exposed: "Median $/W in ZIP 98053 = $3.41 across N=47 quotes". This is the public fruit of the DB. Feeds the landing page and SEO per-ZIP pages.
- **Aggregation is default-ON with no Phase 1 UI** per [ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md). Lawful basis is Art. 6(1)(f) legitimate interests; anonymization is load-bearing. Opt-out plumbing (`users.aggregation_opt_out` + `PATCH /api/me/aggregation` + cascade) is wired from day 1; user-facing toggle deferred to a future settings page.

**Data model (Postgres):**

```
audits (                              -- user-facing record of their audit
  id uuid pk
  user_id uuid fk (nullable for anon)
  created_at
  -- minimal user context:
  location_bucket                      -- ZIP-3 (US) / postcode district (UK)
  tariff_inputs jsonb                  -- user-supplied utility + rates
  user_pii_blob_ref                    -- separate PII vault row; deletable; never joined to installer_quotes
)

installer_quotes (                    -- one row per uploaded proposal PDF; installer-centric
  id uuid pk
  audit_id fk audits                   -- join to user only via audit, never direct user link
  uploaded_at timestamptz
  raw_pdf_storage_url                  -- private, encrypted; auto-purged within 24-72h via TTL job
  raw_pdf_sha256                       -- retained after PDF purge for dedupe + audit trail
  raw_pdf_purged_at                    -- timestamp the TTL job removed the file
  extraction_status                    -- pending | extracted | needs_review | verified
  extraction_confidence jsonb          -- per-field scores

  -- installer identity: RETAINED in full, never exposed externally pre-review
  installer_id fk installers
  quote_date, quote_expiry
  rep_name                             -- internal only; rep direct phone/email NOT stored

  -- location bucketed for privacy (no street address):
  location_country, location_region, location_bucket

  -- extracted system + financials (see field inventory above):
  system_spec jsonb                    -- panels, inverter, battery, mounting, etc.
  financials jsonb                     -- gross, adders, incentives, net, financing, claims
  quoted_metrics jsonb                 -- year-1 kWh, 20-yr savings, payback, escalator, degradation

  -- our counterfactual:
  our_forecast jsonb                   -- year-1 kWh, 20-yr savings, variance per line
  variance_score                       -- summary 0-100

  aggregation_opt_in boolean not null default true   -- per ADR 0005: default ON; per-user opt-out cascades to flip these
)

installers (                          -- canonical registry, retained in full
  id, canonical_name, aliases[], license_numbers jsonb,
  addresses jsonb, phone, website,
  regions_operating[],
  first_seen_at, quotes_count,
  internal_notes                       -- curation scratchpad
)

region_pricing_aggregates (           -- materialized view, refreshed nightly; PUBLIC
  region_key                           -- ZIP-3 / postcode district
  currency,
  n_quotes,                            -- counts only opted-in quotes
  median_dollar_per_watt, p10, p25, p75, p90,
  median_adder_breakdown jsonb,
  common_equipment_tier_distribution jsonb,
  last_updated
)

installer_internal_stats (            -- materialized view; INTERNAL ONLY, never exposed
  installer_id,
  n_quotes, regions_active[],
  median_dollar_per_watt_region_normalized,
  median_year1_overstatement_pct,
  common_adders_pattern,
  quote_evolution jsonb                -- prices over time
)

user_pii_vault (                       -- isolated table; can be purged independently
  id uuid pk, user_id fk,
  full_name, address_full, phone, email,
  created_at, deletion_scheduled_at
)
```

**Privacy & ethics policy (published at launch):**
- Users: we only retain what's needed for forecasting. No street address stored alongside your audit — only a ZIP-3 / postcode district bucket. Your name/email are in a separate vault you can delete at any time without losing the audit itself.
- Raw PDFs are auto-purged within 24-72 hours of upload. The extracted data and your audit results persist. You can also explicitly delete the extracted record at any time.
- Installer data (names, license numbers, quote details) is retained in full, **internally**. Sales-rep direct contact info is not stored. We do not expose named installer statistics at launch. Regional aggregates by ZIP/postcode are exposed; specific installer call-outs are not.
- Aggregation is **default ON** with no Phase 1 UI surface. By default, anonymized pricing from your audit (location bucket, system spec, financials, quoted metrics — never your name, address, or contact info) contributes to the regional benchmark DB. Opt-out is plumbed in from day 1 (a future settings page surfaces the control); contact us in the meantime to opt out.
- No sale of data to lead generators. Ever. Part of the pledge.
- When/if we eventually publish named installer stats, it will be post-legal-review, with a right-to-respond portal, with clear methodology — not at launch.

**Moat compounding:** Each Phase 1 audit contributes one data point to the installer DB and one to regional aggregates. Default-ON aggregation (per ADR 0005) compounds at the full rate of audit volume rather than the opt-in conversion rate; the lawful basis pivots to Art. 6(1)(f) legitimate interests with documented anonymization as the load-bearing mitigation. Combined with Track (actual production data per installer), the internal dataset becomes the industry's most complete installer accountability record — quietly held, available to drive product (BOM suggestions, regional benchmarks) long before it's ever published.

## Files / Patterns to Port from Current Repo

These are reference implementations. Backend code stays Python — straight copy + refactor where sensible. Frontend code is a re-architecture on Next.js + TanStack patterns, so port patterns not code.

| From (current repo) | To (new repo) | Notes |
|---|---|---|
| `backend/services/calculations.py` (degradation, NPV, payback, credit bank) | `backend/engine/steps/degradation.py`, `backend/engine/steps/finance.py` | Pure functions; refactor into pipeline steps, keep as Python |
| `backend/services/amortization.py` (fixed + variable-rate schedules) | `backend/engine/steps/finance.py` | Keep as Python |
| `backend/services/pvwatts.py` (NREL client) | `backend/engine/steps/irradiance.py` (NSRDB provider) | Replace PVWatts-REST with pvlib + NSRDB for US; add PVGIS and Open-Meteo providers |
| `backend/models.py` Loan/LoanPayment | `backend/engine/inputs.py` Pydantic schemas | Keep Pydantic; adapt to multi-user context |
| `frontend/src/lib/format.ts` | `frontend/lib/format.ts` | Port + add multi-currency (USD, GBP) |
| `frontend/src/components/*` (shadcn patterns, dark mode, mobile nav, skeleton loaders) | `frontend/components/*` | UI patterns, not direct copy |
| `frontend/src/api/` TanStack Query hook patterns | `frontend/lib/queries/` | Pattern, not direct port |
| Recharts chart configs (cash flow, monthly bars) | `frontend/components/charts/` | Reusable |

**Do not port:** PSE scraper (WA-specific; Track layer will handle utilities via generic adapters), single-user JWT auth (replaced by multi-user auth in the SaaS — Auth.js or FastAPI magic-link), APScheduler (replaced by proper queue + workers), `OriginalProjection` / `ReforecastYear` single-user models (replaced by per-user audit and track records).

**Port later for Track:** Enphase/Solcast/SolarEdge clients, reforecast engine, scheduler patterns, audit log model, assumption-health tracking.

## Phased Roadmap

pvlib and hourly 8760 simulation are present from Phase 1 (no separate "engine upgrade" phase). Tracker is not a distant v2 — it ships alongside Audit, because both are the same engine and the outcome-data flywheel only starts spinning when Track is live.

| Phase | Scope | Rough effort |
|---|---|---|
| 0. Plan + repo setup | Plan approval, new repo, Next.js container scaffold, FastAPI backend scaffold, Postgres, Dockerfiles, Fly.io deploy, CI | 1-2 wks |
| **1a. Engine + BS-detector plumbing (critical path)** | **pvlib pipeline: irradiance providers (NSRDB/PVGIS/Open-Meteo), DC production (incl. cell-temp + inverter clipping via ModelChain per ADR 0006), soiling + snow (pvlib-backed once monthly weather inputs land), degradation, tariff (flat + tiered + simple-TOU), export credit (NEM 1:1 + NEM 3.0 NBT + UK SEG), finance (loan + NPV + IRR + payback), Monte Carlo wrapper. Port `calculations.py` + `amortization.py` golden-fixture tests from current repo. Async job queue + worker.** | **5-7 wks** |
| **1b. Proposal Audit MVP (HERO)** | **PDF upload (24-72h TTL purge), Vertex AI Gemini extraction pipeline (fields per inventory; ZDR; inline_data), human-in-the-loop correction UI, variance report, heuristic BOM alternative rules, multi-bid comparison view, `audits` + `installer_quotes` + `installers` + `user_pii_vault` + regional aggregates, installer detail retention (internal only, rep direct PII stripped), default-ON aggregation + opt-out plumbing (no Phase 1 UI; per [ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md)). Test suite seeded with user's Puget Sound proposal set.** | **5-7 wks** |
| 2. Auth + Stripe | Auth.js or FastAPI-native JWT + magic link, Stripe checkout (Decision Pack + Founders bundle), entitlements layer, save/revisit audits | 2-3 wks |
| 3a. Decision Pack depth | Scenario diff, battery hourly dispatch (rule-based), TOU tariff refinement, user-configurable discount rate + opportunity-cost overlays, sale-scenario modeling, methodology PDF export, share links, **DSIRE incentives integration (post counsel review)** | 5-7 wks |
| 3b. UK launch | PVGIS adapter already present; add Octopus Agile simulator, SEG picker, MCS toggle, VAT cliff, green mortgages, £ formatting, UK-format proposal extraction templates | 3-5 wks |
| 4. Track MVP | Bill ingestion (Green Button where available; manual entry fallback), inverter monitoring (Enphase + SolarEdge at launch; Tesla Phase 2), variance-vs-forecast dashboard, alert thresholds, subscription billing | 10-14 wks |
| 5. Public launch + content | Landing page ("Plan it. Check it. Track it."), methodology blog, no-lead-gen pledge prominent, ProductHunt/HN, build-in-public changelog. **E&O policy bound before launch push (per Phase 1 closed decisions).** | 2 wks |
| **Post-launch** | Named installer aggregates (once N>20 per installer), right-to-respond portal, SEO per-ZIP/postcode pages from regional aggregates | 4-6 wks |
| **Later** | Independence modeling (battery backup, critical-load panel, outage-duration priors), LP-optimized battery dispatch, Canada + Germany expansion, EV/heat pump loads, AI conversational wizard | TBD |

## Verification

End-to-end checks for each phase:

- **Engine correctness:** Golden fixture tests — feed the current repo's `data/solar_financial_data.json` inputs into the new Python engine, assert NPV/payback/year-1 production match within 1% of current Python output for the overlapping scope. Reuse current repo's 114 backend tests as a spec. Where pvlib outputs differ from the current repo's PVWatts-based outputs (typically 3-8%), document the delta and treat pvlib as the new truth.
- **Wizard UX:** Manual run-through in 3 personas (US homeowner, UK homeowner, advanced prosumer). Verify every input has a default and an explanation tooltip.
- **Multi-region:** Run identical system in WA, CA, TX, London, Edinburgh — verify reasonable production deltas, correct currency, correct incentives applied.
- **Entitlements:** Toggle a feature key from `free` to `decision_pack` in the registry, verify gating immediately reflects in both the frontend `useEntitlement` hook and the FastAPI dependency guard, without any other code changes.
- **Battery dispatch:** Cross-validate 8760-hour output against NREL SAM for 1 reference system; expect within 5% annual savings.
- **Anonymous → save migration:** Run wizard logged out, sign up, verify scenario migrates from localStorage to Postgres intact.
- **Proposal Audit extraction accuracy:** Curate 25 real PDF proposals (5 Sunrun, 5 Tesla, 5 SunPower, 5 EnergySage-marketplace, 5 misc) spanning US + UK. Hand-label ground truth. Extraction pipeline must achieve >95% accuracy on quantitative fields (price, kW-DC, panel count, year-1 kWh claim) with confidence scoring. Low-confidence flagged for user review.
- **Proposal Audit — variance math:** For 10 proposals where we know the actual installed system's year-1 production (from current repo's real data + volunteer users), verify our variance report directionally matches reality (sign + rough magnitude).
- **PII scrubber:** Automated test — upload a proposal with known PII fields (name, address, signature, sales-rep phone/email), verify the sanitized `installer_quotes` row contains none of them — only ZIP/postcode prefix, company name + license #, and rep name (no rep direct contact info).
- **PDF retention TTL:** Automated test — upload a proposal, verify raw PDF is purged from object storage within the configured TTL window, and that `raw_pdf_purged_at` timestamp is set on the `installer_quotes` row.
- **Aggregation default + opt-out:** Automated test — complete an audit; verify the quote appears in `region_pricing_aggregates` (default-ON per [ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md)). Then `PATCH /api/me/aggregation` to opt out; verify cascade flips all the user's `installer_quotes.aggregation_opt_in` to false and the next aggregate refresh excludes them. New audits after opt-out also stay excluded.
- **Data flywheel:** After first 100 opted-in audits, verify regional aggregates compute correctly, benchmarks surface in new audits, no installer appears named until N>20.
- **Cost monitoring:** Confirm fixed vendor run rate stays on free tiers at baseline traffic; alert if any *unexpected* vendor charge appears. Vertex AI Gemini cost per audit is the dominant variable: budget ≤ $2 per audited bid, with a hard alert at $3 (realistic spend on 2.5 Flash is $0.005-0.05 per 10-page audit, so the budget exists primarily as runaway-detection). Typical user runs 1-3 bids per audit session. Weekly spend-per-audit review.
- **Security audit:** Before Phase 5 public launch, engage a consultant for a one-time review focused on (a) PDF parser isolation, (b) API authorization boundaries (per-user row-level access in the application layer), (c) PII-vault cryptographic boundary, (d) Stripe webhook signing, (e) share-link tokens. Budget $3-8k. Follow up with quarterly self-review using OWASP ASVS Level 1.
- **Load test:** Before Phase 5, simulate 500 concurrent wizard sessions + 50 concurrent PDF uploads + 10 concurrent Monte Carlo jobs; confirm API response times hold, queue depth stays under threshold, and Postgres connection pool survives. Identify and document the first scaling bottleneck so we know what to fix at 10× launch traffic.
- **Accessibility:** WCAG 2.1 AA for core flows (landing, wizard, results, audit upload/review). Axe-core automated checks in CI, manual screen-reader walkthrough on results page (where non-sighted users interpreting a variance report is highest-stakes).
- **Legal review gates:** privacy policy and ToS before any email capture; "no lead-gen" pledge wording before any paid-acq channel; named-installer disclosure policy before any aggregate crosses N=20 publicly; GDPR Data Processing Agreement template before any UK Tracker subscriber.
- **Adversarial extraction test:** curate 10 deliberately-misleading PDFs (e.g., "25-yr warranty" footnote contradicting body, hand-written addenda overriding table, password-protected, scanned-not-OCRd, 40-page kitchen-sink). Verify extraction *knows it doesn't know* (confidence < threshold) rather than silently producing a plausible wrong value.
- **Privacy boundary test:** attempt to re-identify a user from the anonymized aggregate data given their system config + ZIP-3. If re-identification is feasible with < 1000 other records in the same bucket, coarsen the bucket or add k-anonymity protection before shipping aggregates.
- **Refund flow:** test end-to-end Stripe refund on Decision Pack triggers immediate entitlement revoke, audit-retention opt-out, and clean-up of cached extraction artifacts.

## Open Items to Decide During Build (product)

Phase 1 closed decisions (PDF retention TTL, aggregation default, LLM vendor, E&O timing) are recorded at the top of this document. Items still open:

- **Hosting provider at launch** — Fly.io (default); AWS Fargate/ECS as the portability target. Container deploys work identically either way
- **Proposal audit geographic launch** — launch US + UK simultaneously if UK extraction templates ship in Phase 3b; otherwise US-only Phase 1, UK in Phase 3b
- **Proposal audit: free first-audit gating** — by IP+cookie+email? Just email? Tradeoff between friction and abuse
- **PDF retention TTL specifics** — 24h vs. 48h vs. 72h within the closed extract-and-delete envelope. Default 72h (gives the user time to fix mis-uploads) unless GDPR review pushes shorter.
- **Equipment DB** — deferred post-launch. Phase 1 BOM suggestions rely on heuristics only. Revisit once audit volume justifies (CEC PV/Storage CSVs + Sandia pvlib built-ins are the obvious seed when we do build it)
- **DSIRE data licensing terms** — defer to Phase 3a; needs counsel review on CC-BY-SA before integration
- **Raw PDF retention edge cases** — what happens to PDFs flagged for manual review within the TTL window? Auto-extend, or escalate to user?

## Repo

User will create a new repo separately. This plan file lives in the current `solar-tracker` repo on branch `product-plan` for reference and review. No code will be scaffolded in the current repo — current repo continues serving personal use.

## Glossary

First-use acronyms collected for skim-readers:

- **BOM** — Bill of Materials (panels, inverter, battery, balance-of-system line items on a quote)
- **CAC / LTV** — Customer Acquisition Cost / Lifetime Value
- **CEC** — California Energy Commission (maintains the PV/Storage equipment eligibility lists)
- **CPUC** — California Public Utilities Commission (NEM rules)
- **DC:AC ratio** — Ratio of DC panel nameplate to AC inverter rating; > ~1.3 invites clipping losses
- **DSIRE** — Database of State Incentives for Renewables & Efficiency (NC Clean Energy Tech Center)
- **E&O** — Errors & Omissions (professional liability insurance)
- **ITC** — federal Investment Tax Credit. The residential Section 25D credit terminated Dec 31, 2025 under OBBBA. Commercial Section 48E remains on its own phase-down schedule (relevant to TPO lease/PPA financing, where third-party owners may pass value through in pricing)
- **LBNL** — Lawrence Berkeley National Laboratory (publishes *Tracking the Sun*)
- **MCS** — Microgeneration Certification Scheme (UK quality mark required for SEG eligibility)
- **MPU** — Main Panel Upgrade (common solar install adder, $2-5k typical)
- **NBT** — Net Billing Tariff (CA's post-April-2023 successor to NEM 2.0; colloquially "NEM 3.0")
- **NEM** — Net Energy Metering (generic term for residential-solar export compensation)
- **NREL** — National Renewable Energy Laboratory (PVWatts, NSRDB, SAM, pvlib upstream funder)
- **PSM3** — Physical Solar Model v3, NREL hourly irradiance dataset
- **SEG** — Smart Export Guarantee (UK: Ofgem-mandated minimum feed-in scheme since 2020)
- **SREC** — Solar Renewable Energy Credit (tradable instrument in certain US RPS states)
- **TMY** — Typical Meteorological Year (8760-hour climatology artefact used for production modeling)
- **TOU** — Time-Of-Use tariff (rate varies by hour/season)
- **URDB** — Utility Rate Database (NREL, canonical US tariff seed)
- **ZDR** — Zero Data Retention (LLM vendor configuration ensuring inputs/outputs aren't logged or used for abuse-detection retention beyond the request)
- **ZFC** — Zero-Framework Cognition (Steve Yegge essay; design principle that puts cognition in models and orchestration in deterministic code)

## Red-Team Appendix — Technical & Execution Concerns

Strategic, market-competitive, and ethical red-team items live in `BUSINESS_PLAN.md`.

### Technical

1. **Engine version drift over time.** pvlib ships updates quarterly; irradiance-source tables refresh; tariff data changes. A user who buys an audit today and re-opens it in 18 months will see different numbers if we silently recompute. Mitigation already in plan: every saved forecast pins engine version + pvlib version + irradiance-source version + tariff-table hash; re-runs are explicit user actions.
2. **LLM extraction accuracy on "typical" proposals is already high; the long tail is where the product bleeds.** Handwritten edits, scanned-not-OCRd uploads, password-protected PDFs, multi-proposal stapled uploads, foreign-language addenda — all produce plausible-wrong extractions. Confidence gating matters more than headline accuracy. Single-vendor Gemini at start removes one redundancy axis; reintroduce Claude fallback if extraction quality plateaus or vendor outage exposure justifies.
3. **Per-installer template caching was considered and rejected (ZFC violation).** Installer templates change 2-4× per year and legacy templates persist for months, so fingerprinting in application code is a template-drift trap. Replaced by tiered-model routing + Vertex AI server-side context caching (same cost benefit from stable prefixes, no brittle fingerprinting). See Cognition Architecture.
4. **PVWatts API rate limits are real and under-addressed.** NREL developer key: 1,000 requests/hour, 5,000/day typical. Every wizard preview + every audit location = 1+ call. At modest traffic (100 concurrent users) we hit ceiling. Mitigation: aggressive lat/lon bucket cache (already planned), but also consider queueing / progressive enhancement.
5. **Long-running compute must be queued, not synchronous.** Hourly 8760 × Monte Carlo simulations take seconds to minutes — far beyond any HTTP request budget on any platform. Architecture commits to POST-to-queue + poll/websocket-for-result from Phase 1 (see Weather & Irradiance implementation sketch).
6. **Postgres storage grows quickly with extraction JSON + hourly result caches.** At ~10KB per audit × 50k audits = 500MB for audits alone; hourly cache snapshots add more. Managed Postgres tiers (Fly Postgres, Neon, RDS) price accordingly; forecast storage costs with audit-volume growth and consider archival / re-compute-on-demand for old audits. Note: extract-and-delete on raw PDFs caps object-storage growth, but JSON extracted data still grows linearly with audit count.
7. **ZIP-3 bucketing may still re-identify in sparse regions.** Rural ZIP-3 can cover fewer than 1k households; combined with system size, panel brand, and approximate install date, re-identification is non-trivial. Either enforce k-anonymity (require ≥ 20 other records in bucket before aggregate publishes) or coarsen to state level in sparse areas.
8. **GDPR retention of installer rep names is awkward.** Individual sales reps are data subjects with rights. "Retained in full, internally" requires a lawful basis under Art. 6 — arguably legitimate interest for accountability, but must be documented and subject to erasure requests. Phase 1 closed decision strips rep direct contact PII (phone/email) at extraction; rep name retention still needs a documented Art. 6 basis.
9. **Single-vendor LLM dependency.** Phase 1 closed decision narrows to Vertex AI Gemini. Vertex outage, regional service issue, or pricing shock all hit extraction directly. Mitigation: monitor extraction success rate + cost daily; have a Claude-fallback router design ready to re-enable (deferred, not deleted); track the cost-redundancy trade-off explicitly.

### Execution / roadmap

1. **Phase 1a + 1b = 8-11 weeks for "hero feature working well" is optimistic for PDF extraction at 95% accuracy across varied formats.** Real-world experience from receipt/invoice OCR products (Dext, Expensify) suggests 3-6 months to production quality on a single document class. Plan for Phase 1b to slip, and design the Phase 1a scope so it's shippable as a wizard-first MVP if audit extraction isn't ready.
2. **UK launch "2-3 weeks" understates tariff/regulatory data effort.** Octopus Agile modeling alone is a 1-2 week engineering task, and the whole UK stack (PVGIS, SEG picker, MCS, VAT cliff, green mortgages, £ formatting, UK proposal extraction) is 4-6 weeks realistic. Re-estimate Phase 3b.
3. **v2 Tracker "8-12 weeks" covers four inverter vendors + two utility APIs + reforecast — optimistic.** Each inverter integration (Enphase, SolarEdge, Tesla, GivEnergy) is 1-2 weeks with OAuth + token refresh + error handling + back-fill. Re-estimate Tracker at 14-18 weeks.
4. **No explicit beta/private-access phase.** Launch sequence jumps from internal dog-food to public launch without a ~20-50-user closed beta. Insert a closed-beta phase between Phase 4 (Track MVP) and Phase 5 (public launch) for extraction-accuracy tuning and testimonial capture.
