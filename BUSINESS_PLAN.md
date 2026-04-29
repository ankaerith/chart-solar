# Solar Forecast Product — Business Plan

> **Note on scope**: `VISION.md` is the strategic north star. This document holds the business case — competitive analysis, market sizing, pricing/tiers, success metrics, team, business-side risks. Feature scope, architecture, and engineering verification live in `PRODUCT_PLAN.md`. Legal and IP risk is in `LEGAL_CONSIDERATIONS.md`. Where this document and VISION.md conflict, VISION.md wins.

## Context

The current `solar-tracker` is a polished single-user living financial model for one residential PV+net-metering investment (PSE/WA). It works well for personal use but every public "solar calculator" online is either oversimplified or a thinly disguised installer lead-gen funnel. There is a structural gap: no consumer SaaS does for solar what **ProjectionLab** does for retirement planning or **Monarch Money** does for budgeting — a transparent, sophisticated, no-lead-gen tool that lets a homeowner build a real forecast, then track whether it's actually working.

This business case evolves the project into that product. We fork into a new repo, build the planner + audit first, and the tracker ships alongside it (the three modes — Explore, Audit, Track — share one engine and one product, per VISION.md). Codebase strategy: keep the current repo as the personal/reference implementation; reuse calculation logic and UI patterns from it but rebuild on a modern, portable SaaS stack.

## Competitive Analysis

### Planner market — what exists today

| Competitor | Type | Pricing | Honest planner? | Key gaps |
|---|---|---|---|---|
| **EnergySage** | Marketplace + calculator | Free (installer pays $40-120/lead) | No — lead-gen; Schneider majority-owned | No TOU, no battery dispatch, flat 2.2% escalator, no NEM 3.0, 20-yr savings routinely 15-30% overstated |
| **Project Sunroof** (Google) | LIDAR roof estimator | Free | Partially — but abandonware | Data last refreshed 2019-21, no battery, no TOU, no financial depth |
| **SolarReviews** | Reviews + calc | Free (lead-gen) | No | ~8 inputs, funnels to quote form |
| **Solar.com** (ex-Pick My Solar) | Pure lead funnel | Free | No — VC-backed lead-gen, $100-200/exclusive lead | Calculator is a qualification shell |
| **Tesla Solar** | OEM direct | Free | No — Tesla-only funnel | Savings frequently criticized as 30% optimistic on r/TeslaSolar |
| **Sunrun / SunPower** | OEM direct | Free | No — sales qualifier | Bill-only input → sales call |
| **NREL PVWatts** | Gov research tool | Free | Yes — but bare-metal | Single-page, no save, no tariff, no battery, no UI |
| **NREL SAM** | Gov research desktop | Free | Yes — gold standard physics | Desktop-only, ~60 inputs, engineering literacy needed; ~30-50k global users, ~zero consumers |
| **Aurora Solar** | Installer SaaS | $200-500/seat/mo | N/A — installer tool | Sales Mode is in-home; no consumer access; acquired HelioScope 2022 |
| **HelioScope** | Installer SaaS | $159-$249/seat/mo | N/A | Installer-only |
| **OpenSolar** | Free installer SaaS | Free (monetizes hw/finance referrals) | N/A | Consumer only sees installer-branded proposal |
| **Pylon** | Aurora challenger | $99-$149/seat/mo | N/A | Installer-only |
| **HahaSmart / UnderstandSolar** | Consumer calc | Free (lead-gen) | No | Declining traffic; absorbed into lead networks |
| **Geostellar** | Failed indie attempt | N/A | Yes (shuttered ~2019) | Raised $17M, failed on CAC — instructive |

**UK:**

| Competitor | Type | Pricing | Honest planner? | Key gaps |
|---|---|---|---|---|
| **Energy Saving Trust calc** | Gov-adjacent default | Free | Yes-ish | Conservative, tariff-agnostic, no Agile, no battery dispatch |
| **Solar Together** (iChoosr) | Council group-buy | Free | No — quote funnel | Not a real calculator |
| **Octopus Energy Solar** | Utility-bundled | Free | Partial — captive to Octopus | Only models Octopus tariffs + Octopus install |
| **Sunsave** | 20-yr subscription | Free calc | No — sells own sub | Front-loads sub vs buy |
| **Eco Experts / GreenMatch / Solar Guide / EffectiveHome** | Lead funnels | Free (£40-120/lead) | No | Thin qualification forms |
| **Good Energy / E.ON / EDF / British Gas / OVO** | Utility quote forms | Free | No | Quote generators, not planners |
| **PVGIS** (EC tool) | Gov research | Free | Yes — but bare-metal | No financials, no UK tariffs, no battery |

**Adjacent "indie SaaS" playbook** (the template we're copying):

| Product | Price | ARR (est.) | What we learn |
|---|---|---|---|
| **ProjectionLab** | $9/mo · $108/yr · $249 lifetime | ~$1M ARR, solo-built by Kyle Nolan | Transparent assumptions, local-first, public changelog, build-in-public, "free tier is actually useful". Note: their monthly sub works because retirement planning is inherently recurring — solar is not, which is why we shift to one-time + tracker-sub |
| **TurboTax / H&R Block** | $40-120 one-time per year | $3B+ | Pay-at-decision-time works for high-stakes, infrequent decisions — the solar planner fits this pattern better than a subscription |
| **Monarch Money** | $14.99/mo · $99.99/yr | Captured Mint refugees | Users pay for boring utility software when incumbent betrays trust |
| **Boldin** (ex-NewRetirement) | $120/yr · $1,500/yr advisor | Deep Monte Carlo planner | Sophistication sells — if UX respects the user |
| **Maxifi** | $109-$149/yr | Kotlikoff economics-PhD brand | Power users love it; UX is a wedge |

**Tracker-side (v2 competitors):** Enphase Enlighten, SolarEdge Monitoring, Tesla app, Solar Analytics (AU), Sense, Emporia, GivEnergy app, Home Assistant Energy, PVOutput.org, Loop/Hugo/Bright (UK smart-meter apps). **None close the loop on "is my investment performing vs. the pro-forma I was sold."** That variance-vs-forecast reconciliation is genuine whitespace.

### Industry dynamics driving the gap

1. **Lead-gen economics warp every consumer calculator.** Installer CAC is $1,500-3,000/sold customer. Lead brokers sell raw leads at $40-120 shared, $150-300 exclusive. Every input field exists to qualify lead quality, not to inform the homeowner. This is structural, not a UX oversight.
2. **Trust has measurably broken down.** Multiple sources document systematic overstatement of production and savings in residential solar proposals: LBNL's *Tracking the Sun* (pricing/configuration trends), Wood Mackenzie residential-PV reports, Berkeley Lab's PV performance studies, and NREL field-measurement papers consistently show measured year-1 output below nameplate-times-PVWatts expectations (typical shortfall 5-15%, highest under aggressive DC:AC ratios, shading, or soiling the proposal ignored). Twenty-year savings projections are separately inflated when installers use flat ~2.2%/yr utility escalators (while PG&E/SCE authorized 8-15%/yr increases in GRC cycles 2022-2024 — high escalators help payback look fast, but installer defaults often *understate* escalation), or when they ignore CA's NEM 3.0 post-April 2023 export de-rate. Specific percentage claims ("15-30% overstated," "85-92% of proposal") must be re-verified with primary citations before they appear in marketing.
3. **NREL builds excellent physics (PVWatts, SAM, pvlib) nobody wraps in a consumer UI.** SAM users are academics and utility-scale engineers. The consumer wrapper opportunity is wide open.
4. **UK market has no ProjectionLab-equivalent at all.** Utility-bundled tools are captive; EST is conservative and tariff-agnostic; lead-gen dominates the rest. Unit economics are better in UK (Octopus API free, Hildebrand/n3rgy smart-meter data free, no expensive UtilityAPI equivalent required).

### Why a homeowner pays $79 when free calculators exist

- Stakes are 250-500× the one-time fee ($20-40k purchase decision).
- Existing free tools demonstrably overpromise (LBNL data, CA NEM 3.0 threads, Reddit "EnergySage vs. reality" archives).
- One-time fee matches how people research solar: intense 2-8 week period, then decide. No monthly-sub commitment friction during the research window.
- Proposal audit alone plausibly worth $79 — auditing a $25k purchase for surprises is table-stakes financial hygiene (pre-purchase home inspection analog).
- Trust is a durable moat: the no-lead-gen pledge is a position incumbents can't credibly take because it contradicts their revenue model.
- Tracker sub ($9/mo) picks up post-install users who want ongoing optimization — natural upsell from Decision Pack cohort.

### Positioning — named wedges with evidence

1. **"Your installer's proposal, audited" (HERO WEDGE)** — upload the PDF quote your installer handed you; we extract the bill of materials (BOM), back-test production/savings claims against PVWatts + utility time-of-use (TOU) + realistic degradation + actual Net Energy Metering (NEM) rules, and hand back a line-by-line variance report with specific renegotiation points and alternative BOM suggestions. Directly attacks the LBNL-documented 8-15% production overstatement and EnergySage-style 15-30% savings overstatement. **Unique in the market** — no existing tool audits a proposal; EnergySage collects competing quotes, no one critiques the one in your hand. The data flywheel from every upload seeds a regional cost-of-solar DB and installer knowledge base no competitor can catch up to — a compounding moat. This is the primary landing-page offer.
2. **"NEM 3.0 honest calculator" (California-specific wedge)** — explicitly model CA's Net Billing Tariff (NBT, formally "NEM 3.0") export compensation using Avoided Cost Calculator hourly values (export credits typically ~60-80% lower than retail, varies by hour/season; do not hard-code a single "75%" constant in the engine), battery arbitrage under TOU, show the delta vs. EnergySage. Evidence: CPUC Dec 2022 decision (D.22-12-056); ongoing r/solar CA complaint volume; no consumer competitor does this correctly. Note: states still on NEM 1.0/2.0 (most of US) keep retail-rate export; the wedge is CA-centric plus early analogs in NC, NV, HI, and future state copycats.
3. **"Octopus Agile simulator"** — half-hourly import/export modeling with battery dispatch under Agile + Outgoing. Nobody, including Octopus's own tool, does this for non-Octopus customers across suppliers.
4. **"VAT 2027 cliff countdown + green mortgage integration"** — UK-specific: surface 0% VAT sunset (31 Mar 2027, per HMRC), fold in Nationwide/NatWest/Barclays green mortgage rate discounts into payback. No tool does this. Re-check the sunset date quarterly — HMRC has extended similar reliefs before, and a policy change invalidates landing-page copy overnight.
5. **"Show your work" methodology panel** — every constant editable, every source cited, exportable PDF. ProjectionLab playbook applied to solar. Defensible against LLM-generated clones because it requires curated tariff/incentive data, not just UI.
6. **Calibration loop (Track)** — re-fit the model to actual inverter + utility data. Retention engine + data moat. When combined with the proposal-audit DB, closes the ultimate accountability loop: "Installer X's proposals average 14% above year-1 actuals" — a killer feature no incumbent can credibly build.

### Risks (cross-cutting register)

| Risk | Likelihood | Mitigation |
|---|---|---|
| Aurora / OpenSolar moves downmarket | Low (structural mismatch: their ACV is $2-3k/yr, serving $9/mo cannibalizes nothing) | Monitor; own the consumer brand before they try |
| Octopus bundles an Agile calculator | Medium (UK) | Stay supplier-agnostic; model all SEG options; be ally not competitor |
| LLM-generated clones flood the market | High but shallow | Moat = curated tariff/incentive DB + proposal-audit data flywheel + calibrated physics + brand trust, not UI. Clones can't reproduce proprietary regional quote DB |
| Lead-gen calculators improve | Low (structurally can't be honest) | Not a real threat |
| NREL releases a better consumer tool | Low (25 years of PVWatts suggests no) | Contribute upstream, stand on their shoulders |
| EnergySage adds a real planner tier | Medium | They can't credibly drop lead-gen; trust position remains ours |
| **PDF extraction accuracy on varied installer formats** | **High at launch; diminishes with data** | Claude vision + structured tool-use extraction; ZFC-compliant tiered routing (Haiku → Sonnet → Opus); hybrid escalation (deterministic floor + model-declared confidence); human-in-the-loop correction UI for critical fields below confidence bar; Anthropic server-side prompt caching for stable prefixes (not application-level template fingerprinting). See PRODUCT_PLAN.md §Cognition Architecture. |
| **Defamation / legal risk from naming individual installers** | **Medium if named too early** | Phase 1: aggregate-only (no installer names on public stats until N>20 quotes per installer). Phase 2: factual statements only, sourced to our own data, clear methodology. Legal review before any named disclosure. Safe harbor: opinions + sourced data + right-to-respond process |
| **Installers refuse to honor quotes we've flagged / push back publicly** | **Low-Medium** | Frame as "questions to ask your installer," not accusations. Provide installer right-to-respond portal. Aggregate transparency is a net good for reputable installers (they look comparatively great) |
| **Regulatory: state contractor boards on "consumer advice"** | **Low** | We're software tooling, not advisors; disclaimer; don't replace engineer sign-off |
| **Privacy: quote PDFs contain PII (name, address, signature)** | **High** | Extract + discard PII before any aggregation; user controls what's stored; opt-in for contributing to transparency DB; separate PII-containing raw PDF from sanitized quote record; GDPR/CCPA compliant from day 1 |
| **State-level policy churn** (NEM rule cuts, property-tax-exclusion sunsets, state-credit appropriation lapses) | **Medium** | Treat each state's incentives as date-parameterized inputs; surface policy risk on results; maintain a policy-change changelog per jurisdiction. Do not depend on any single credit for product viability. Federal residential ITC already terminated (Section 25D, end of 2025); plan is designed for the post-ITC environment |
| **NREL / Octopus / PVGIS API Terms of Service restrictions on commercial use** | **Medium** | Read each ToS before launch; NREL Developer Portal requires attribution and rate-limits; Octopus API is free but ToS-bounded; PVGIS is public-domain. Budget for commercial-grade fallbacks (Solcast, Meteostat Pro) if ToS bites |
| **LLM API cost creep on PDF extraction** | **Medium-High** | Per-audit spend budget (target <$2); hard cap per session; fall back to lower-tier Haiku model on known templates; monitor token spend weekly; user-visible "re-run" button costs another audit credit (prevents mis-click abuse) |
| **LLM extraction hallucinates plausible-but-wrong values on atypical proposals** | **High** | Confidence thresholds that hard-block variance reports without user review on critical fields; adversarial test set (hand-crafted misleading proposals); always show "extracted → user-verified" state on the variance report |
| **Insurance / E&O exposure: audit influences $25k+ purchase** | **Medium-High** | Phase 1 launch: deferred (see closed Phase 1 decisions in PRODUCT_PLAN.md). Bind a policy before Phase 5 public-launch push or 50 paid audits/mo, whichever first. Clear "not financial/engineering advice" disclaimer on every report from day 1; maintain methodology archive for audit defence; indemnification clause in ToS |
| **State contractor-board interpretation of "consumer advice" as regulated activity** | **Low-Medium** | CA CSLB, NV contractor board, etc. occasionally challenge non-licensed "solar consultants." Product is software; do not offer human-advised consulting. Legal counsel review in Phase 2 before marketing push |
| **Share-audit-links with installer name trigger defamation / tortious-interference claim** | **Medium** | Share links anonymize installer by default; named version requires opt-in + right-to-respond completion. Do not allow public posting of audit URLs until legal review |
| **Google AI Overviews / SGE absorb organic search traffic** | **Medium-High** | Content strategy assumes Google delivers ~30-50% less click-through than historical; diversify across Reddit, YouTube, referral loops, direct brand |
| **Hosting cost creep as compute load grows** (hourly sim × Monte Carlo × monitoring ingestion) | **Medium** | Model cost-per-active-user at each tier; track Fly/AWS spend per audit + per Track user weekly; optimize hot paths before upgrading instance sizes; cache irradiance and simulation intermediates aggressively |
| **Malicious PDF uploads (XFA, embedded JS, XXE)** | **Low-Medium** | PDF parsing in isolated worker; disable JS execution; file-size and page-count caps; virus scan (ClamAV) on ingestion; never render uploaded PDFs inline to other users |
| **Solar industry downturn (rates up → residential PV orders down)** | **Medium** | 2024 saw ~20% YoY residential install decline in US. Plan for 18-month runway of reduced demand; tracker sub retains installed-base users even if new-install market contracts |

## Positioning

**Tagline:** *"Plan it. Check it. Track it. — the honest math for your roof, before, during, and after."*

Supporting line when more context is needed: *"Build a real forecast for your home, see every assumption, then track whether it's working — without anyone trying to sell you a system."*

**Differentiated moats** (synthesizing the analysis above):

1. **Proposal Audit + regional quote data flywheel (primary moat)** — upload installer PDF, get a calibrated second opinion AND alternative BOM suggestions. Every audit contributes (opt-in) anonymized pricing to a regional cost-of-solar DB and installer knowledge base. The data compounds: more audits → tighter benchmarks → better BOM suggestions → more viral sharing → more audits. No incumbent can replicate this because (a) EnergySage/Solar.com are incentivized to keep pricing opaque, (b) new entrants need years of quote volume to catch up. This is the hero feature and the strongest competitive moat the product has.
2. **Model transparency as product** — every assumption editable, sourced, with confidence ranges; "show your work" methodology export.
3. **Scenario engine** — diff cash vs loan vs PPA vs subscription, with/without battery, sizing variants, tariff plan changes, EV add-on. Save/version/share.
4. **NREL-grade physics in a consumer UI** — PVWatts/PVGIS irradiance + clipping + soiling + temperature derating + degradation + hourly battery dispatch; plug-in pattern for future refinements.
5. **Multi-region from MVP** — US (with NEM 3.0 modeled correctly) + UK (with Octopus Agile / SEG / VAT cliff / green mortgages) day one.
6. **No lead-gen pledge** — stated loudly on homepage, in privacy policy, in methodology. Structural moat vs. incumbents.
7. **Calibration loop (Track)** — re-fit the model to actual inverter + utility data. Combined with the audit DB, creates the ultimate accountability signal: installer-level variance between quoted and actual year-1 production.

## Tier Structure

Critical requirement: features must be easy to move between tiers. Single `entitlements` table maps feature keys → plan tiers, checked via a typed `useEntitlement('battery_hourly_dispatch')` hook on the client and middleware on the server. Stripe products map to plan tiers, **not individual features**, so promote/demote is a single DB row change.

**Pricing model rationale:** Solar purchase is a one-shot decision. A monthly sub for the planner mismatches user behavior (most people decide, buy, and don't come back). Tracking, by contrast, is genuinely recurring — especially for UK Agile users who re-optimize tariffs and dispatch. So: **one-time fee for the planner, monthly sub for the tracker.** This is closer to TurboTax (pay at decision time) than ProjectionLab (ongoing life planning).

| Tier | Price | Includes |
|---|---|---|
| **Anonymous** | Free, no account | Sample audit walkthrough (pre-generated), regional $/W benchmark lookup by ZIP/postcode, basic PV forecast for a hand-entered system (no PDF upload), 25-yr cash flow, sign-up to save |
| **Free (account)** | $0 | 1 saved scenario, basic PV forecast (PVWatts/PVGIS), simple loan, 25-yr cash flow, payback/NPV, plain-English verdict, regional $/W benchmarks. **No PDF audit** (LLM cost gate). |
| **Decision Pack** | **One-time $79** (or £69) — lifetime access | **Proposal Audit: PDF upload + extraction + variance report + BOM alternatives + multi-bid compare.** Unlimited scenarios + diffing, battery hourly dispatch, TOU / Octopus Agile / NEM 3.0 modeling, clipping/derating tuning, state + local incentives (SRECs, state credits, UK SEG + green mortgages + VAT cliff), methodology PDF export, share links. Buy once when shopping; refer back whenever. |
| **Track (subscription)** | **$9/mo · $89/yr** (US), **£6/mo · £59/yr** (UK) | Inverter sync (Enphase, SolarEdge, Tesla, GivEnergy), utility data sync (UtilityAPI, Octopus, n3rgy), variance-vs-forecast alerts, calibrated reforecast, Agile tariff optimization, multi-property |
| **Founders / Lifetime bundle** | **$249 one-time** (launch only, capped units) | Decision Pack + Tracker for 5 years (not literally "lifetime" — that phrase creates an uncapped support liability and sours unit economics if ARPU erodes). ProjectionLab-style goodwill + upfront cash; drives launch momentum. Cap at first 500 buyers or 90 days, whichever hits first. At 5 × $89 = $445 list, the bundle delivers a 44% discount — generous without collapsing LTV. |

**Why this works better than pure sub:**
- Matches user behavior (one-shot purchase research).
- Single purchase at decision time is an easier conversion than a monthly sub commitment from someone mid-research.
- Removes churn concern for the planner side (non-issue if pricing is one-time).
- Tracker sub retains only those who got value from install — self-selecting, higher LTV:CAC.
- Decision Pack buyers become warm leads for Tracker post-install (natural upsell funnel).
- Founders bundle drives early cash + word-of-mouth.

**Revenue modeling (rough, stress-tested below).** Scenario math, not a forecast:

| Scenario | Annual site traffic (unique researchers) | Decision Pack conv. | Decision Pack rev | Tracker conv. of DP buyers | Tracker ARR | Total yr-1 gross |
|---|---|---|---|---|---|---|
| Bear | 20k | 1% = 200 | $16k | 5% = 10 | $0.9k | ~$17k |
| Base | 100k | 2% = 2,000 | $158k | 10% = 200 | $17.8k | ~$176k |
| Bull | 300k | 3% = 9,000 | $711k | 15% = 1,350 | $120k | ~$831k |

The base case implies 100k unique researchers/year finding the site — which requires either organic SEO maturity (typically 12-18 months of content investment before this traffic is achievable) or paid acquisition at a CAC that still clears the $79 ticket. See Market Sizing & Customer Acquisition below for the unresolved CAC question. Tracker gross margin ~65-90% depending on region. Unit economics work at modest scale if (and only if) CAC stays below ~$25 blended — not a venture-scale business but a healthy indie-SaaS one if acquisition math holds, matching the ProjectionLab template.

Initial feature gates (movable later):
- **Free:** wizard, 1 scenario, basic forecast, simple loan, plain verdict, regional $/W benchmarks (read-only, seeded by anonymized audit data)
- **Decision Pack (one-time):** **proposal audit (PDF upload/extraction/variance/BOM alternatives/multi-bid)**, scenario branching/diff, battery, TOU/Agile/NEM 3.0, clipping/derating editing, PDF exports
- **Tracker (monthly):** inverter sync, utility sync, variance alerts, reforecast

**Why audit is fee-gated, not free:** each audit costs real money in LLM tokens (Claude vision for PDF extraction: ~$0.05-0.50 per proposal depending on page count, plus downstream analysis calls). A free-first-audit model invites abuse and erodes unit economics on the primary value-delivery step. Instead, free tier gets the *fruit* of the DB (regional benchmarks) and a sample audit walkthrough; paid tier gets their own audit. This aligns cost with willingness-to-pay: users holding a $25k quote are the ones who need the audit and will pay $79.

## Market Sizing & Customer Acquisition

The plan's revenue arithmetic hinges on traffic and conversion assumptions that need explicit top-down validation.

### Top-down TAM / SAM / SOM

| Layer | US | UK |
|---|---|---|
| Residential PV installs per year (2024-25 baseline) | ~650-800k systems (SEIA/Wood Mackenzie) | ~180-230k (MCS Installations Database) |
| Households currently *researching* solar (12-month horizon, estimate from EnergySage + DOE survey data) | ~3-5M | ~0.8-1.2M |
| Addressable with a paid audit (researchers with a concrete quote in hand) | ~600-900k US | ~150-250k UK |
| SOM at year-3 equilibrium (1-2% of addressable) | 6-18k Decision Pack buyers | 1.5-5k |
| SOM revenue at $79 / £69 | $0.5-1.4M | £0.1-0.3M |

This is a credible low-seven-figures opportunity in steady state. It is *not* venture-scale (hundreds of millions ARR) and the plan should not pretend otherwise. The indie-SaaS template is the right fit.

### Customer acquisition plan (currently the weakest part of the plan)

Honest acknowledgement: the plan assumes inbound traffic will materialize and does not cost the work to get it. Concrete channels and their realistic cost/timeline:

| Channel | Realistic timeline to meaningful volume | Blended CAC target | Risks |
|---|---|---|---|
| SEO: per-ZIP / per-postcode benchmark pages | 9-18 months for content to rank; needs ≥ N quotes per region first (chicken-and-egg) | $0 marginal, ~$10-30k content investment | Google AI Overviews may absorb the query without sending clicks |
| SEO: "how to read a solar quote" / "NEM 3.0 explained" evergreen content | 6-12 months | Same as above | Competing with installer-funded content farms |
| Reddit (r/solar, r/ukSolar, r/TeslaSolar, r/Octopus_Energy) | Immediate, trust-based, un-scalable | $0 but bounded | Community rules — posting product links is often banned; "build-in-public" founder presence is the only playbook |
| Product Hunt / Hacker News | One-time spikes (~2-10k visitors over 48h), poor downstream conversion to solar buyers (wrong audience) | Effectively $0 | HN audience researches but rarely installs in the 30-day window |
| YouTube partnerships (e.g., Matt Ferrell "Undecided," ThisWeekInSolar, Artisan Electric) | 3-6 months to land first partnership; $500-5k/video | $15-40 if it works, unbounded downside | Creator concentration risk |
| Google Ads on "solar quote review" / "is my solar quote fair" | Immediate, measurable | $8-25/click; $200-800 CPA at 3-10% landing conversion | CPCs inflate fast as installers defend SERPs |
| Meta Ads retargeting | After seed traffic exists | Moderate | Poor cold-audience performance for high-consideration purchases |
| Solar forums / Facebook groups (Enphase/Tesla/Agile user groups) | Slow, high-trust | ~$0 marginal | Requires persistent community presence |
| MoneySavingExpert (UK) / Which? partnerships | If earned, transformative for UK | Revenue share | Editorial, not paid — long relationship-building |

**The key unresolved question: what's the blended CAC?** At $79 Decision Pack with ~90% gross margin, we can afford ~$25-35 blended CAC to stay healthy once Tracker LTV lift is counted. Google Ads at $400+ CPA make the unit economics work only if Tracker attach is >40%, which is speculative. Plan must *test* paid acquisition in a $5-10k trial before Phase 5 launch, not after.

### Seasonality and latency

Solar research is highly seasonal (peaks March-June in UK, April-August in US) and heterogeneous by state incentive calendars (CA pre-NEM-3.0 rush was 10× baseline). Any ARR projection needs to net against this — do not straight-line monthly visitors.

### Retention / churn

For Tracker sub, churn has not been modeled. Relevant benchmarks:
- Boldin / ProjectionLab: ~3-5% monthly for broad financial planners
- Solar-specific monitoring (Sense, Solar Analytics): ~1-2%/mo once installed, homeowners "set and forget"
- Assumption for model: 2%/mo blended, reviewed at month 6 with real data

At 2%/mo churn, LTV(Tracker) ≈ $89/yr × 1/(0.02×12) ≈ $370. This is the number that justifies CAC spend; set target CAC:LTV at 1:3 → CAC ceiling $120 for Tracker — but Tracker users are primarily acquired from Decision Pack funnel, so the relevant question is *incremental* CAC to convert DP → Tracker (nearly $0 if done well via in-app prompts at install time).

## Operating costs at launch

Honest fixed + variable cost picture, drawn from the stack choices in `PRODUCT_PLAN.md`:

- **Fly.io baseline**: ~$5-20/mo for a small API + worker + Postgres footprint (scale-to-zero Machines help during low traffic)
- **Resend / Sentry / Plausible**: all free-tier to start
- **LLM spend for PDF extraction**: Gemini 2.5 Flash on Vertex AI — ~$0.005-0.03 per audited bid (10-page typical). At 100 audits/month early-access, expect $1-30/mo
- **Stripe**: ~2.9% + $0.30 per transaction
- **Domain + legal review**: one-time $500-2k
- **E&O insurance**: deferred at Phase 1 launch (see Phase 1 closed decisions in PRODUCT_PLAN.md). When bound: ~$100-250/mo

Practical first-year run rate: **~$50-200/month variable** until meaningful paid volume, scaling with audit count. Gemini's ~10× cost advantage over Claude on PDF extraction means LLM spend is no longer the dominant variable cost; Postgres + bandwidth dominate at scale.

## v2 Tracker unit economics

At $19/mo Pro tier, API cost stack per active tracker user:
- **US:** Enphase free, SolarEdge free, Solcast commercial ~$0.50-2/mo/user at scale, UtilityAPI ~$3-4/mo/account → **~$4-6/user/mo** data cost. Gross margin ~65-75%. Arcadia likely unaffordable until Series A.
- **UK:** Octopus API free, Hildebrand Glow / n3rgy free (consented), Solcast ~$0.50-2/mo → **~$1-2/user/mo**. Gross margin ~90%. **UK has materially better tracker economics; consider UK-first on v2.**

## Success Metrics, Kill Criteria & Monitoring

Pre-commit to what "working" looks like so we can recognise "not working" honestly.

### North-star metric
**Paid audits completed per month** (not MAU, not visits). This compounds every other metric — pricing validation, acquisition health, extraction quality, word-of-mouth — into one number.

### Tiered success thresholds
| Horizon | Green (ship more, expand) | Yellow (diagnose) | Red (pivot / kill) |
|---|---|---|---|
| 90 days post-launch | ≥ 50 paid audits, ≥ 20 Tracker signups | 10-49 audits | < 10 audits |
| 180 days | ≥ 200 audits, ≥ 60 Tracker signups, ≥ 1 organic referral ≥ 10 users | 50-199 audits | < 50 audits |
| 365 days | ≥ 1,000 audits, ≥ 300 Tracker active, CAC:LTV ≤ 1:3 | 300-999 audits | < 300 audits or CAC > LTV |

### Supporting metrics
- **Audit-to-Tracker conversion rate** (target ≥ 8% at 12 months post-install of the audited system)
- **Extraction accuracy on quantitative fields** (target ≥ 95% without user correction; measured weekly on a held-out labeled set)
- **Median audit session time** (target 5-15 minutes; >30 min signals friction, <3 min signals non-engagement)
- **LLM cost per audited bid** (target ≤ $2; alert > $3)
- **Regional aggregate coverage** — count of postcodes with N ≥ 5 quotes (the SEO / benchmark moat metric)
- **Customer-support contacts per audit** (target ≤ 5% of audits open a ticket; high values signal UX failure)
- **Refund rate** (target ≤ 5%; > 10% means the product isn't delivering perceived $79 value)

### Kill criteria (explicit)
Pre-commit to these so sunk cost doesn't drag the project past viability:
1. **< 10 paid audits in the first 90 days post-launch** with baseline traffic: acquisition thesis failed; pause feature work, investigate channel. If no viable channel surfaces in 60 more days, sunset.
2. **Extraction accuracy stuck < 85% on quantitative fields after 200 real proposals and two iteration cycles:** core value prop is not defensible; consider pivoting to guided-entry rather than PDF-extraction.
3. **Refund rate > 20%** sustained: product is not delivering perceived value; refund everyone, take down paywall, re-scope.
4. **Legal cease-and-desist from 2+ installers within first 6 months** that cannot be settled with our right-to-respond process: exposure outweighs moat; rethink disclosure model entirely.
5. **CAC:LTV remains worse than 1:1.5 after 12 months** with all reasonable channel experiments tried: business model doesn't work at this price point; consider agency / white-label pivot.

### Monitoring
- **Cost tracking:** daily Fly.io (or AWS) + Anthropic + Stripe spend aggregated to a single dashboard (Metabase or Grafana against Postgres); weekly digest email
- **Error tracking:** Sentry free tier (5k events/mo)
- **Uptime:** Upptime or Better Uptime free tier
- **User analytics:** Plausible (privacy-friendly) once traffic > a few hundred/day; no Google Analytics (brand-consistent with no-lead-gen ethos)
- **Extraction-quality regression:** weekly batch over labeled held-out set; alert if accuracy drops > 2% week-over-week

## Team & Resource Plan

Currently missing from the plan. Minimum viable team posture to ship as scoped:

| Role | Phase 0-3 | Phase 4-5 | Post-launch | Notes |
|---|---|---|---|---|
| Engineering (full-stack) | 1 FTE | 1 FTE | 1-1.5 FTE | Solo-founder pattern à la ProjectionLab is plausible; avoid premature hires |
| Design | Contract ~10 hrs/week | Contract | Hire at $500k ARR | Start with shadcn/ui defaults + light polish |
| Legal | Project-based (~$5-15k) | Project-based | Retainer at $1M ARR | Privacy policy, ToS, named-installer review, UK GDPR |
| Content / SEO | Founder-led + contract writer | Same | Hire at $300k ARR | Methodology posts, per-region benchmark pages |
| Customer support | Founder | Founder | VA / support hire at 500 MAU | Intercom free → Plain at scale |
| Accounting / tax | Project-based | Project-based | Fractional CFO at $500k ARR | Critical for multi-region VAT/sales tax |

**Cash runway minimum:** 12 months of ~$4k/mo burn (founder unpaid, tools + legal + LLM spend + paid-acq trials) = ~$50k. If this is not available before Phase 1, descoping or delaying Phase 1b is safer than half-shipping.

## Open Items (business)

- **Decision Pack price point** — $79 recommended; test $49 / $99 landing pages pre-launch
- **Refund policy** — 30-day no-questions (ProjectionLab pattern); reduces first-purchase friction
- **Founders bundle cutoff** — first 500 buyers, or first 90 days (launch milestone)
- **Named installer aggregate threshold** — N=20 per installer is a reasonable starting line, revisit with legal before shipping
- **Installer right-to-respond portal** — required before any named disclosure; design in Phase 2, launch with v2.5
- **Stripe product structure** (one-time Decision Pack + subscription Tracker + bundle SKU)
- **Domain name + brand**
- **Privacy policy / no-lead-gen pledge wording** (legal review)
- **Whether to open-source the engine** (community trust + LLM-clone moat tradeoff; recommend yes once stable — contributes credibility)
- **Whether to upstream tariff contributions to pvlib / SAM** for goodwill

## Red-Team Appendix — Business Concerns

This section collects critiques raised during review that were not resolved by the edits above. They are issues the business should confront during the build, not decided here. Technical and execution-related red-team items live in `PRODUCT_PLAN.md`.

### Strategic / business-model

1. **"Indie SaaS" comparison is apples-to-oranges on TAM.** ProjectionLab addresses ~every US household saving for retirement (~60M). Honest solar planner addresses ~households researching solar in a 12-month window (~3-5M US). Even identical conversion yields ~15× smaller top-line. The ceiling of the business is real (low-seven-figures ARR at steady state) and the plan should stop implying otherwise.
2. **The flywheel is N-gated before it produces moat.** Regional benchmarks need N ≥ 5-10 per ZIP to be trustworthy; N ≥ 20 to be publishable. At realistic launch volume (~50-100 audits/month), only 2-3 metros reach N ≥ 20 in the first year. Landing-page copy implying "regional benchmarks" is a check we may not cash for 6-12 months. Consider seeding with publicly-scraped sample quotes (check ToS first).
3. **Wedge conflict: "audit the installer" vs. "help homeowners decide."** These are different user states. A homeowner with no quote yet can't use the hero feature; a homeowner with a quote already has intent and some trust in their installer. The wizard path and audit path are parallel products sharing an engine, not one funnel. This is fine, but the landing page and onboarding must not pretend otherwise.
4. **"No lead-gen pledge" is a durable moat only as long as founder ownership is maintained.** If the product is ever acquired, that pledge is the first thing to collapse. Consider encoding the pledge in legal structure (e.g., B-corp, revenue-share commitment, or a charter clause).
5. **Founders bundle cap is essential.** Without a hard numeric cap on units sold, the bundle is a long-tail support liability. Edit above sets 500 units / 90 days; enforce this in the Stripe product, not prose.
6. **Proposal audit is a *transactional* product, Tracker is a *relational* product.** The hoped-for DP → Tracker conversion is a very different buying decision 3-9 months later, often after install pain or delight has recalibrated the user's trust in software. Do not assume natural-funnel certainty.
7. **Insurance is a gating requirement, not nice-to-have.** Software that influences a $25k purchase decision with specific recommendations on specific named installers is an E&O target. Phase 1 launch deliberately defers a policy (see PRODUCT_PLAN.md closed decisions). Calendar trigger before Phase 5 public launch or 50 paid audits/mo, whichever first.

### Market / competitive

1. **OpenSolar is already closer to consumer than "installer-only" implies.** Some OpenSolar proposals are homeowner-visible via shared links and include interactive scenario tweaks. The product has consumer-facing presence through installer-branded funnels; moat is narrower than stated.
2. **Tesla vertical integration is an underrated structural competitor.** Tesla can bundle solar + Powerwall + grid-service revenue (e.g., VPP participation) in a way the honest planner cannot model cleanly without Tesla-specific data cooperation — which Tesla has no incentive to give.
3. **Aurora's consumer play could come via SolarRev acquisition or similar.** Their installer-facing tool has the physics; the missing piece is consumer UX, which they could buy cheaply. Track acquisition rumors.
4. **The content moat depends on Google sending traffic.** AI Overviews / SGE increasingly answer "is my solar quote fair" without sending a click. Plan assumes SEO as the main organic channel but does not quantify this risk.
5. **UK's Octopus is a friend-or-foe decision.** Plan says "stay supplier-agnostic; be ally." Fine, but Octopus has an installation business (Octopus Solar) and could quietly de-prioritize the Agile API for third parties. No written ToS protection exists.

### Ethics / brand

1. **The tool produces a verdict that can destroy a sale.** If the audit says "this is bad, renegotiate," the homeowner will act on it. If the audit is wrong (extraction error, missing local-tariff detail), the homeowner may lose a good install or sour on solar entirely. The product's ethical obligation is to be conservative in negative verdicts and transparent about uncertainty.
2. **"Worth it?" plain-English verdict can be legally fraught depending on phrasing.** "Not worth it" → potential negligent-misrepresentation exposure if wrong. Prefer "Here's what we see" / "Questions to ask" language over imperative verdicts.
3. **Aggregation default for contribution** is a closed Phase 1 decision: default ON, no Phase 1 UI surface, opt-out plumbing in place (see [ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md), which supersedes ADR 0002). Lawful basis under UK GDPR pivots to Art. 6(1)(f) legitimate interests with documented anonymization (ZIP-3/postcode bucketing, no homeowner identifiers, k-anonymity gate). Trades a tighter LIA + UK pre-launch revisit for full-rate moat compounding.

### Writing / structure (minor)

1. Acronym density remains high; skim-readers will bounce. Glossary lives in PRODUCT_PLAN.md; consider a "TL;DR" at the top of both docs.
2. The Competitive Analysis tables cite specific prices ("$40-120/lead," "£1,400-£1,800/kWp installed") that will rot in 12 months. Date-stamp each table or move pricing to a separate living doc.
