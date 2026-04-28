# Vision

**Plan it. Check it. Track it.** — the honest math for your roof, before, during, and after.

## Problem

Residential solar is sold on 25-year financial promises built from optimistic assumptions: rate-escalation forecasts that exceed historical CAGR, production estimates that overstate the roof, and savings projections that quietly compound both. The homeowner has no independent way to check the math before signing, and no way to check whether reality matched the promise after install. Installers have marketing. Lenders have amortization tables. Utilities have rate cases. The consumer has nothing.

## Product

One economics engine, three user modes, one cross-cutting axis — what the user optimizes for.

### Explore — "Should I go solar?"

Self-serve forecast. The user enters an address and uploads a recent utility bill. The engine runs an independent production model (PVWatts + Google Sunroof shading) and a Monte Carlo rate-escalation simulation against the household's actual usage. Output is a distribution of 25-year financial outcomes, not a single headline number. No proposal required.

### Audit — "Check this proposal."

Same engine, run against the installer's claimed system size, production estimate, and escalation assumption. Produces a side-by-side diff: where the installer's math differs from independent benchmarks, by how much, and which levers drive the gap.

### Track — "Did it actually work?"

Post-install subscription. Ingests utility bills and inverter-monitoring data (Enphase, SolarEdge, Tesla at launch). Reports monthly variance against the Explore forecast or the audited proposal — both bill-level ("is my wallet on track?") and production-level ("is the system underperforming?"). Coaches escalation to the installer when variance exceeds warranty thresholds.

Audit is Explore plus a proposal diff. Track closes the loop and feeds real outcome data back into Explore's priors.

### Values

A short onboarding captures whether the user optimizes for financial return, energy independence, or environmental impact — usually a weighted mix rather than a pick-one. All three modes honor the weighting.

- **Financial-first**: sizing caps at the utility's NEM buyback rate, battery is scrutinized as an ROI drag, the headline output is the NPV distribution.
- **Independence-first**: sizing prioritizes outage resilience and self-consumption, battery is sized for backup coverage rather than payback, the headline output is days-of-backup plus self-consumption ratio.
- **Environmental-first**: sizing fills the usable roof, generation is weighted by marginal grid emissions (hourly CO2 factor), the headline output is lifetime tCO2 offset.

The same proposal can be a red flag under one lens and a green flag under another — an oversized system over-sells for a financial-first user and is correctly sized for an independence-first user. Flag ranking and caveat ordering follow the weights. In Track, the primary variance metric re-indexes the same way: wallet-variance for financial, production-variance plus backup-availability for independence, on-track-offset for environmental.

Financial and environmental outputs ship at launch. Independence modeling lands in Phase 2 alongside battery dispatch, outage-duration priors, and critical-load panel modeling.

## Financial model

The engine produces a personal capital-allocation analysis, not a single payback number. Product personality is closer to an interactive planning tool than a verdict generator: same data, multiple framings, user in control of the assumptions that matter to them.

### Cash-flow fidelity

- **Hourly 8760 simulation from launch.** Production × usage × tariff × export rules computed hour by hour, for 25 years. Required for post-NEM-3 California, time-of-use arbitrage, and any honest battery self-consumption math. Not optional.
- **Monte Carlo** across weather-year, rate-escalation path, degradation rate, hold duration, and remaining policy tail risks. Output is a distribution, not a point estimate.
- **Tax-event accuracy.** Credits, rebates, SREC income, and property-tax exclusions modeled at actual tax years, not day-one net-offs.

### Metrics surfaced

- **Cumulative net-wealth trajectory** per scenario (do-nothing / cash-own / loan-own / TPO-lease / TPO-PPA), with the user's alternative-investment returns overlaid as comparison lines.
- **NPV distribution** at a user-configurable discount rate.
- **LCOE vs. utility rate trajectory** — shows the crossover year when solar beats grid $/kWh.
- **IRR / MIRR** with reinvestment-rate caveat stated explicitly.
- **Discounted payback** (not raw payback).
- **Tornado sensitivity** ranking inputs by outcome impact.

Hero view is user-selectable among cumulative wealth, scenario summary cards, and NPV distribution. Same underlying model, three framings.

### Opportunity cost

Users enter a personal discount rate or pick a preset benchmark: HYSA / T-bill rate, their actual mortgage APR, long-run equity index return, or their loan APR if financing. The cumulative-wealth chart overlays the same capital deployed in each alternative. Users see directly whether solar wins or loses against their real alternatives — rather than against zero, which is the installer-calculator default.

### Sale-scenario modeling

Hold duration is probabilistic (ZIP-defaulted, typically 10–15 years for US owners). Expected outcomes probability-weight across hold distribution. A "sell in year X" view models solar home-value uplift (~$4/W per peer-reviewed studies), remaining loan balance, assumable-vs.-payoff rules, and buyer-market conditions. Installers never show this; it's often the dominant risk.

### Financing audit

- **Dealer-fee detection.** Solar-specific loans often embed 20–30% fees in the system price, turning a 3.99% APR into an effective 8–10% real cost of capital. Flagged when the proposal pattern matches.
- **TPO (lease/PPA) audit.** Escalator terms, buyout schedule, title-transfer conditions, production-guarantee enforceability.

## Positioning

Consumer Reports with an NPV engine. Published methodology, planner-nerd delivery. Named practices, never named companies. Regulator-friendly voice. No affiliate revenue, no lead-gen handoff to installers, no referral fees.

## Who it's for

US homeowners evaluating or recently installing rooftop solar. Primary persona: the over-researcher — the person who reads r/solar, collects three quotes, and suspects the sales pitch. Secondary: the post-install owner who feels the promised savings haven't shown up.

## Moat

Outcome-data flywheel. Track benchmarks real post-install performance against forecasts; that ground truth sharpens Explore and Audit priors in ways a GPT wrapper cannot copy without equivalent install-base coverage. Secondary durability: the niche is too small for VCs to chase and too unsexy for incumbents to defend.

## Three-year ceiling

Rooftop-plus-garage bundle. Solar, storage sizing, EV-tariff economics. The household transaction is drifting from "install panels" to "electrify the home," and the engine extends naturally to battery dispatch modeling and EV-charging tariff optimization.

## Markets

US first. Enphase and SolarEdge dominate US residential monitoring and are well-documented; NEM and utility rate schedules are public. UK is Phase 2: different inverter mix (GivEnergy, Solis, Growatt), different rate regime (Ofgem price cap, Octopus TOU tariffs), different incentives (SEG vs. NEM). Separate market, separate launch plan, shared engine core.

## Top-of-funnel

Free public tool: utility rate-escalation lookup. ZIP or postcode returns the historical CAGR and a forecast band for that utility. Reuses the rate-forecast database built for the paid engine. Acts as an SEO asset and email-capture surface without cannibalizing the paid product.

## Data layer

The modeling commitments imply a specific data stack:

- NREL TMY + hourly solar radiation (free, public).
- Hourly residential load archetypes (ResStock / DOE by ZIP × square footage × heat source) with Green Button import as an upgrade path where utilities support it.
- OpenEI URDB for tariff schedules, plus hand-curated NEM 3 / net-billing / export-rate rules per utility.
- State incentive and SREC databases (DSIRE as starting point; curation required).
- Solar home-value uplift references ($/W peer-reviewed studies, Zillow-style regional data).
- Inverter-monitoring APIs: Enphase, SolarEdge, Tesla at launch.

## Stack

Maximally portable. No provider-proprietary features in the hot path.

- **Frontend**: Next.js 15 (App Router) — SSG for marketing/content surfaces, client components for the authenticated app. Deployed as a Node.js container. No Vercel-proprietary features (Edge runtime, KV, Blob, ISR-specific semantics, Vercel Cron).
- **Backend API**: FastAPI (Python). Auth, CRUD, job dispatch, result queries.
- **Compute workers**: Python, shared codebase with the API. Hourly 8760 simulation, Monte Carlo, pvlib-based production modeling. Separate worker entrypoint from the API.
- **Queue**: Redis + RQ or Dramatiq. Portable to SQS on AWS via one adapter.
- **Database**: Postgres. Self-hosted, managed (RDS, Fly Postgres, Neon, Supabase Postgres using portable features only).
- **Object storage**: S3-compatible (R2, S3, GCS). PDF uploads, export artifacts, cached irradiance snapshots.
- **Hosting**: containers on Fly.io initially. AWS Fargate/ECS or any container host is a drop-in target; moving providers is ops work, not code work.

UI inside the Next.js app: TanStack (Query / Router / Table / Form / Virtual), Recharts for financial visualizations, shadcn/ui + Tailwind for components.

## Honest limits

- Named practices, never named companies. No watchdog posture.
- Distribution of outcomes, not investment advice.
- Audits what's in the proposal, not what a salesperson said verbally.
- Track requires supported inverter brands at launch; unsupported systems get bill-only variance.
- The build is real. Hourly simulation + Monte Carlo + sale-scenario modeling + monitoring integrations at launch is a 9–12 month focused effort, not a weekend project. The positioning ("we did the hard math") only holds if the math actually gets done.
- A meaningful share of Explore outputs will recommend "not now" or "only via lease." That's on-brand, and will dampen conversion relative to installer-aligned tools.

## Deferred

- Pricing calibration for the Audit one-shot and the Track subscription.
- Launch sequencing between the free escalation tool and the paid engine.
- Monitoring-API integration order beyond the top three vendors.
- Monte Carlo stochastic-axis scope — which variables are sampled vs. held deterministic, and sample count per report.
- Battery dispatch modeling approach — rule-based (charge off-peak, discharge at peak) vs. LP-optimized (~3–5% accuracy delta, ~10× compute cost).
- Default-vs.-surfaced-input hierarchy — with this many dials, most must default intelligently; which knobs are user-facing vs. hidden under "advanced."
- Onboarding length — capturing values weights, discount rate, financing type, hold duration, usage pattern, and roof details without drop-off. Needs progressive disclosure philosophy.
