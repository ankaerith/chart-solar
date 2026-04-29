# Legal & IP Considerations

> **Status**: Research compilation, not legal advice. Items marked "lawyer review" should be cleared with outside counsel before launch. Prepared 2026-04-22, drawing on the data-source inventory in `VISION.md` and `PRODUCT_PLAN.md`.

This document inventories every external data source, library, API, and content type referenced in the product plan, and assesses commercial-use, redistribution, attribution, and IP risk for a paid consumer SaaS (`$79` one-time Decision Pack + `$9/mo` Tracker subscription, US + UK launch).

---

## Top 10 risks (ranked)

| # | Risk | Source / area | Severity |
|---|---|---|---|
| 1 | **Raw installer-PDF retention** — copyright + GDPR/CCPA exposure on long-term storage of installer-copyrighted documents | User-uploaded content | **High** — fix with extract-and-delete policy (~24-72h TTL) |
| 2 | **DSIRE CC-BY-SA 4.0 ShareAlike** — can contaminate proprietary incentive DB if redistributed | DSIRE | **High** — avoid embedding; scrape primary state sources instead |
| 3 | **Google Solar API ToS use-case mismatch** — limited to feasibility/design/sales; production-tracking arguably outside scope, plus `$0.10–$0.75`/call | Google Solar API | **High** — already deferred in plan; confirm avoid |
| 4 | **MCS Installations Database** — ToS prohibits commercial reuse without paid agreement | UK MCS | **High** — seek data agreement or skip; seed UK benchmarks from user uploads only |
| 5 | **Wood Mackenzie / SEIA SMI report quotations** — paywalled enterprise reports actively enforced | Industry reports | **High** — only quote SEIA's free executive-summary figures with required attribution |
| 6 | **Sales-rep PII aggregation** (name + direct contact + performance signal) | User PDFs / installer DB | **High** — strip rep contact PII at extraction; defer named-rep analytics + DPIA |
| 7 | **Reddit scraping** — DMCA §1201 + Responsible Builder Policy actively litigated 2025 | Competitive scraping | **High** — manual reading only; no automated ingestion |
| 8 | **OpenSolar proposal-link crawling** at scale | Competitive scraping | **High** — only analyze proposals user actively uploads |
| 9 | **Solcast per-site pricing for Tracker** — ToS forbids cross-user reuse from one account | Solcast | **Medium-High** — economics don't support `$9`/mo; use Open-Meteo or NSRDB instead |
| 10 | **PII leakage to LLM vendors** (PDFs contain homeowner names, addresses, utility account #s) | AI / Gemini + Claude APIs | **Medium** — fix via Vertex AI ZDR + Anthropic ZDR; scrub rep PII before prompt |

**Note on LLM AUP "financial advice" classification**: our LLM role is **extraction only** (structured fields out of a PDF); the audit verdict is computed by deterministic Python. The vendor AUP clauses on personalized financial advice / high-risk-domain automated decisions therefore don't attach — the Services are used for document parsing, not for generating recommendations. The disclaimer on the audit output stays (good practice + user transparency), but it's not AUP-compliance-critical. This framing should hold across Gemini, Claude, and OpenAI equally; confirmation with counsel is still on the open-questions list.

Plus several **medium** items requiring vendor contracts at scale: UtilityAPI (`~$3`/customer/month eats one-third of Tracker ARPU), SolarEdge (site-owner-key model brittle without ISV agreement), Tesla Fleet API (strict redistribution + termination risk), Google Geocoding 30-day cache rule, Met Office DataHub, n3rgy commercial tier.

---

## Section A — NREL / DOE / US government data

| Source | License | Commercial | Redistribution | Verdict |
|---|---|---|---|---|
| NREL Developer Portal (PVWatts v8, etc.) | Public-domain-ish ToS; PVWatts® registered TM | Yes | Yes | **Safe** — no endorsement language; 1k req/hr default |
| NSRDB / PSM3 | CC-BY (4.0 on OpenEI) | Yes | Yes | **Safe** — cache aggressively; PSM3 download API has tight per-key daily caps |
| OpenEI URDB (US tariff DB) | CC0 1.0 | Yes | Yes | **Safe** — most permissive in stack; no attribution required |
| NREL SAM | BSD-3-Clause | Yes | Yes | **Safe** — ship license notice if binary distributed |
| pvlib-python | BSD-3-Clause | Yes | Yes | **Safe** — bundled Sandia + CEC tables also redistributable |
| DOE ResStock / End-Use Load Profiles | CC BY 4.0 | Yes | Yes | **Safe** — pin a release; cite Wilson et al. / NREL |
| **DSIRE** (incentives) | **CC-BY-SA 4.0 + paid API** | Yes (with copyleft) | Yes (ShareAlike on derived outputs) | **Lawyer review** — copyleft can attach to your incentive tables; consider primary-source curation instead. API subscription `~$5–25k/yr`. |
| Green Button Connect My Data | Per-utility data-access agreements | Yes, but per-utility paperwork | Usually restricted | **High operational cost** — use UtilityAPI as aggregator at MVP; consider DMD (manual XML upload) |
| LBNL Tracking the Sun **dataset** | CC BY 4.0 | Yes | Yes | **Safe** — derive your `$/W` benchmarks from this, not from the report PDF |
| LBNL Tracking the Sun **report PDF** | CC-BY-NC-ND | **No commercial use of PDF figures** | No derivatives | **Cite, don't reproduce** |
| LBNL Hoen et al. ("Selling Into the Sun", `~$4/W` premium) | US Gov license + UC Regents copyright | Yes — citable | Cite, don't republish raw dataset | **Safe to cite** with date caveat (data 2002–2013); pair with newer corroborating source |
| NREL Solar Cost Benchmark reports | US Gov work + CC-BY data | Yes | Yes | **Safe** — standard NREL/DOE attribution |

**Key actions:**
- Replace DSIRE as proprietary embedded source. Either (a) pay for the API and accept CC-BY-SA on rendered output, or (b) curate incentives manually, link out to DSIRE for detail.
- Build `$/W` regional benchmarks from the Tracking the Sun **dataset** (CC-BY), never the report PDF (CC-BY-NC-ND).
- For Green Button: ship Download My Data (manual XML upload) at MVP; defer Connect My Data per-utility onboarding to post-PMF or use UtilityAPI.
- Cache NSRDB hits by lat/lon grid cell — never per-user live PSM3 queries.
- Add `/credits` page listing NREL, LBNL, pvlib, SAM, NSRDB, OpenEI URDB, ResStock with proper attribution.
- Never claim NREL/DOE/LBNL endorsement in marketing.

---

## Section B — International weather & irradiance

| Source | License | Commercial | Cache + cross-user | Cost | Verdict |
|---|---|---|---|---|---|
| **PVGIS** (JRC) | CC BY 4.0 | Yes | Yes | Free, ~30 req/sec/IP | **Safe** — credit JRC/EC |
| **ERA5 / ERA5-Land** (Copernicus CDS) | Copernicus Licence (royalty-free, perpetual) | Yes | Yes | Free | **Safe** — required attribution string: *"Generated using Copernicus Climate Change Service information [Year]"* |
| **CAMS Solar Radiation** (ECMWF ADS) | Copernicus Licence (CC-BY) | Yes | Yes | Free | **Safe** (use ADS direct, not SoDa mirror) — primary irradiance source for UK |
| **NOAA / NWS / NSRDB** | US Public Domain (17 USC §105) | Yes | Yes | Free | **Safe** — strongest commercial posture; don't use NWS logo without permission |
| **Open-Meteo** | CC BY 4.0 data + AGPL-3.0 software | **Free tier non-commercial only** | Yes on paid tier | `€29+/mo` Standard | **Needs paid tier** — API Standard mandatory once a paying customer is onboarded; AGPL only triggers if self-hosted |
| **Met Office DataHub** (UK) | Crown Copyright; bespoke commercial license | Paid tier required | Commercial contract only | GBP 4-5 figs/yr | **Skip for MVP** — DataPoint retired; Site-Specific free tier explicitly non-commercial |
| **Solcast** | Per-site paid; residential free is single-user, 10 req/day | Cross-user reuse from one account explicitly prohibited | No on free; per-site on paid | `$$$` per site | **Avoid** — economics don't fit `$9`/mo SaaS |
| **Meteonorm** | Commercial EULA (Meteotest AG) | Paid | Raw data redistribution prohibited; derived outputs OK | CHF 700 one-time or subs | **Avoid for MVP** — overlaps with free CAMS/NSRDB/PVGIS |

**Recommended stack at launch:** PVGIS (EU/UK) + ERA5 (global historical) + CAMS Solar Radiation (UK irradiance) + NSRDB/NOAA (US) — covers both target markets free with clean commercial reuse. Add Open-Meteo Standard only if you want a single unified forecast API.

**Operational must-dos:**
- Hard-code `source_license` + `attribution_string` columns on every cached TMY row; surface in every export/PDF/API response.
- Quarterly check of [Copernicus License page](https://apps.ecmwf.int/datasets/licences/copernicus/) — §10 reserves unilateral revision.
- Separate cache buckets per source so a future license change invalidates one slice only.

---

## Section C — Utility, tariff, and incentive data

| Source | License/ToS | Commercial | Verdict |
|---|---|---|---|
| **UtilityAPI** (US) | Per-customer authorization; commercial allowed | Yes | **Safe** — but `$3/meter/month` PAYG ≈ 33% of `$9` Tracker ARPU; model unit economics; M&A auto-terminates authorizations |
| **Arcadia (Arc)** | Custom enterprise contract | Paid | **Avoid until post-PMF** — likely 5-figure annual minimums |
| **Green Button CMD** | Per-utility data-access agreements | Yes, per utility | **Use aggregator (UtilityAPI) at launch**; per-utility onboarding is a sales/legal lift, not an API integration |
| **Octopus Energy API** (UK) | Free; key-per-customer | Tolerated for Octopus customers | **Safe for customer-specific use**; Agile/wholesale data cannot be redistributed across non-customers (EPEX/Nord Pool restriction) |
| **Hildebrand Glow / n3rgy** (UK) | Consumer free; n3rgy enterprise SaaS for commercial | Paid (n3rgy enterprise) | **Needs paid tier + UK GDPR/SEC compliance review** |
| **Ofgem** (UK price-cap data) | Open Government Licence v3.0 | Yes | **Safe** — required attribution: *"Contains public sector information licensed under the Open Government Licence v3.0."* Quarterly scrape. |
| **CPUC Avoided Cost Calculator** (NEM 3.0) | CA public domain | Yes | **Safe** for redistributing numeric vectors; do **not** redistribute the E3-authored Excel workbook verbatim |
| **CEC Solar Equipment Lists** | Mixed: Public Records Act data + third-party ToS | Ambiguous | **Lawyer review** for heavy redistribution; **safe** as internal equipment-DB seed with attribution |
| **NREL URDB** | CC0 | Yes | **Safe** — default US tariff seed |
| **SREC markets** (SRECTrade / Xpansiv / LevelTen) | Proprietary; redistribution prohibited | No | **Avoid** redistributing indices; **safe** to use state-PUC public auction clearing prices |
| **MCS Installations Database** (UK) | ToS prohibits commercial reuse without permission | No (default) | **Lawyer review + paid data agreement** required for any commercial use beyond per-user lookup |

**Cross-cutting actions:**
- Sign UtilityAPI (US) + n3rgy enterprise (UK) as aggregators to avoid per-utility paperwork.
- Counsel review on DSIRE ShareAlike (Section A) before any DSIRE API subscription.
- Model `$3`/user/month UtilityAPI cost into Tracker pricing; consider prepaid tier at scale.
- Strip E3 branding from CPUC ACC workbooks before redistributing values.
- Always pull UK SEG rates from primary Ofgem / supplier pages, never from MoneySavingExpert/Which?.

---

## Section D — Inverter monitoring APIs

| Vendor | Commercial path | Auth | Pricing | Verdict |
|---|---|---|---|---|
| **GivEnergy** (UK) | Open, self-serve, encouraged | Homeowner-generated bearer token | Free | **Safe** — easiest integration; UK-only hardware |
| **Solis / Ginlong** | Email application, fast approval | HMAC-signed; per-station | Free | **Safe with caveats** — rough docs; Chinese parent (data residency optics) |
| **Enphase Enlighten** | Self-serve registration, paid plan + signed license required for production | OAuth 2.0, homeowner-granted | `~$80/mo` base + per-system surcharge on commercial tiers | **Safe for personal-production use; lawyer review for installer-benchmarking** ("partner disparagement" clause) |
| **SolarEdge** | Site-owner API key (no formal ISV path self-serve) | Per-site API key | Bundled with monitoring; no published per-call fees | **Workable at launch / needs paid partnership long-term** — historically C&Ds for high-volume aggregation; 300 req/day/site cap |
| **Tesla Fleet API** | Gated approval + one-time partner fee + signed key | OAuth + request signing | Partner fee `~$75` + per-call fees on some endpoints | **Lawyer review / avoid at launch** — strictest redistribution terms; "no competing product" clause; termination-for-convenience risk |
| **Growatt** | Official: gated, slow. Unofficial ShinePhone scrape: ToS violation | Official: API key. Unofficial: user credentials | Free (negotiated) | **Avoid at launch** — official path slow; unofficial is unacceptable for paid SaaS (CFAA + credential storage) |

**Launch order:**
- **Tier 1 (at launch):** Enphase (core variance only), GivEnergy, Solis.
- **Tier 2 (post-launch):** SolarEdge via site-owner keys + ISV agreement pursued in parallel.
- **Tier 3 (v2 / revenue-justified):** Tesla Fleet API, Growatt official partnership.
- **Cross-cutting**: the installer-benchmarking feature ("Installer X is 14% high") needs a dedicated legal pass against **each** vendor's current agreement. Enphase + Tesla specifically have partner-disparagement clauses.

---

## Section E — Google services, geocoding, property data

| Source | Commercial use | Cost | Verdict |
|---|---|---|---|
| **Google Solar API** | Restricted to feasibility / design / sale (not production-tracking) | Building Insights `$0.10-0.20`/call after free tier; Data Layers `$0.30-0.75+`; 30-day cache cliff | **Avoid** — matches existing plan decision; ToS use-case mismatch is the primary reason, cost is secondary |
| **Project Sunroof** | No public API; consumer-facing only | N/A | **Avoid** as data source; safe to reference factually |
| **Google Geocoding API** | Allowed, billed | `$5/1k` requests | **Paid tier required** — store **Place ID** (allowed indefinitely), not lat/lng (30-day delete rule). Or capture user-entered coords once and skip Google entirely. |
| **Zillow / Bridge API** | Effectively gated to MLS/brokerage; `$500+/mo` minimums | High | **Avoid** — not realistic for consumer SaaS |
| **Redfin Data Center** | ToS conflict — page invites use, ToS prohibits commercial reuse | Free | **Lawyer review** for live ingestion; **safe** to cite high-level regional figures with attribution |
| **LBNL Hoen ($4/W premium)** | US Gov license; cite freely | Free | **Safe to cite** with "per 2015 LBNL" framing + newer corroboration |
| **Mapbox satellite imagery** | Allowed, billed | Tile-based pricing; 750k/mo free tier | **Paid tier required**; friendlier than Google for cache rules |
| **OSM + Microsoft US Building Footprints** | ODbL (copyleft) | Free | **Safe with attribution**; review ODbL share-alike before publishing derived datasets |
| **USGS 3DEP / UK EA LIDAR** | Public domain (US) / OGL (UK) | Free | **Safe**; engineering-heavy if used for shading. Not MVP. |
| **Overture Maps Foundation** | CDLA-Permissive 2.0 / ODbL | Free | **Safe** — modern alternative |

**Recommended substitution for "Google Sunroof shading" in VISION.md:** user-entered shading (none/light/heavy) + PVWatts modeling + optional USGS 3DEP lidar for power-user auto-shading in v2. For the home-value pitch, cite LBNL Hoen with date caveat and render as a cited estimate, not a computed line item — minimizes liability.

---

## Section F — User-uploaded installer PDFs & competitive scraping

### F1. Installer proposal PDFs (highest-stakes category)

The installer's PDF is copyrightable (expressive elements: prose, layout, branded chart design). Pricing data, panel specs, output estimates are **facts** (Feist) and not copyrightable. Our copyright posture:

- **Ingest + analyze + return audit**: defensible **fair use** (Authors Guild v. Google, Perfect 10 v. Amazon analogues). User-driven upload, single-document analysis, transformative output (critique, not substitute). Thomson Reuters v. ROSS (Feb 2025) is the main contrary precedent but turned on direct competition with the source — we don't compete with installer-proposal generation.
- **Retention strategy is the single biggest risk lever**:

  | Retention | Copyright | GDPR/CCPA | Breach radius |
  |---|---|---|---|
  | Indefinite | **Highest** | Highest | Entire PDF |
  | 30-90 days | Moderate | Moderate | Bounded |
  | **Extract + delete within 24-72h** | **Low** | Low | Minimal |

  **Recommendation: extract structured fields + audit output, delete PDF within 24–72 hours, keep only (a) SHA-256 hash for dedupe, (b) extracted facts, (c) generated audit.**

- **Aggregate benchmarks** ("median `$/W` in ZIP 98053"): Feist-clean. Don't publish single-proposal quotes with installer names attached pre-launch.
- **Sales-rep PII** (name + direct phone/email + performance signal): personal data under GDPR + post-CPRA CCPA. Strip rep contact info at extraction. Keep company name + license # for audit output. Defer named-rep leaderboard + run a DPIA before reviving.
- **"Confidential" footers / no-share clauses**: footer declarations are not contracts. Even signed clauses bind the homeowner, not us (no privity). Mitigation: ToS warrant clause + auto-flag of "confidential" markings + user one-click confirmation.
- **Do not train any model on user PDFs** without separate, specific, revocable opt-in.

### F2. Competitive scraping (US legal landscape)

- **Van Buren v. United States (2021)** narrowed CFAA "exceeds authorized access" to a gates-based reading.
- **hiQ v. LinkedIn** held public-data scraping doesn't violate CFAA; **but hiQ settled $500k on contract claims** — ToS-based contract claims remain the primary risk.
- **Meta v. Bright Data (Jan 2024)**: logged-off scraping of public pages did not breach Meta's ToS (ToS applied to "users," scraper never logged in).
- **Reddit v. Perplexity (Oct 2025)**: DMCA §1201 anti-circumvention theory, explicitly targeting Google-SERP-based scraping as paywall circumvention.

| Target | Verdict |
|---|---|
| **EnergySage** public/marketing pages, logged-off, polite rate | Acceptable risk with mitigations |
| **EnergySage** calculator/quote flows | **High risk — avoid**; cite EnergySage's own blog/press posts instead |
| **SolarReviews** factual ratings as inputs | Acceptable risk |
| **SolarReviews** verbatim review text or leaderboard reproduction | **Avoid** |
| **Solar.com** automated calculator scraping | **High risk — avoid** |
| **OpenSolar** user's own proposal | Safe (handled under F1) |
| **OpenSolar** mass-crawl of shared proposal links | **High risk — avoid** (matches Reddit v. Perplexity fact pattern) |
| **Aurora / HelioScope** platform scraping | **Avoid** — credentials required, CFAA exposure |
| **Reddit** automated ingestion (any route, including SERP) | **High risk — avoid**; manual reading only |
| **MSE / Which?** scraping | **Avoid** — go upstream to Ofgem / supplier pages |

**Operating rules**: only scrape public, logged-off pages; respect robots.txt; honest UA; low rate (~1 req/several seconds/host); no proxy rotation; stop on C&D.

### F3. Industry research reports

| Report | Verdict |
|---|---|
| LBNL *Tracking the Sun* (figures + dataset) | **Safe** with attribution |
| Wood Mackenzie residential-PV reports (paywalled) | **High risk — avoid** unless licensed; paraphrase only from Wood Mac's own free press posts |
| SEIA / Wood Mac *Solar Market Insight* (free executive summary) | **Acceptable** — quote exec-summary figures only with attribution `"Wood Mackenzie/SEIA U.S. Solar Market Insight®"`; no chart reproduction |
| NREL Solar Cost Benchmark | **Safe** — US Gov work, freely citable |
| Berkeley Lab PV performance studies (Hoen et al.) | **Safe** to cite headlines and methodology; re-render charts rather than lift images |

### F4. US vs. UK differences

| Item | US | UK/GDPR |
|---|---|---|
| Scraping public data | hiQ/Bright Data/Van Buren shield; contract risk persists | Computer Misuse Act 1990 stricter; UK GDPR adds personal-data hook |
| Fair use for analysis | Four-factor flexible | "Fair dealing" only — narrower; commercial uses rarely covered |
| Sales-rep PII | CCPA applies post-2023 (B2B exemption sunset) | UK GDPR; legitimate-interest assessment required |
| Benchmark publication | Feist protects facts | UK Database Right gives extra protection to compilations |
| Proposal PDF analysis | Fair use defense | No analogue — rely on customer-agent framing + minimal retention |

---

## Section G — AI / LLM / infrastructure licenses

### G1. Anthropic Claude API

**AUP scope — why the "high-risk financial advice" clause doesn't attach here:** Anthropic's AUP classifies *"investment advice, loan approvals, determining financial eligibility or creditworthiness"* as High-Risk Use, requiring disclosure + qualified-professional review. **Our use is document extraction only** — the LLM parses structured fields from the installer's PDF (panel count, price, kW-DC, year-1 kWh claim, etc.), and deterministic Python (pvlib + NPV/IRR math) computes the audit verdict. The Claude Service is therefore being used for OCR-with-structure, not for generating personalized financial recommendations. AUP High-Risk clauses target what the Service is used for, so extraction-only use stays outside the classification.

**Architectural discipline that keeps it that way:**
- LLM inputs: the PDF and a schema-constrained extraction prompt. **Never**: "is this proposal a good deal?"
- LLM outputs: typed structured data (Pydantic/JSON). **Never**: prose verdicts, "worth it" opinions, ranked alternatives.
- Flag generation, ranking, ask-your-installer questions: allowed from the LLM *if* grounded in deterministic counterfactual values we computed (per PRODUCT_PLAN.md §Cognition Architecture). These are model-generated *explanations* of deterministic findings, not model-generated *advice*. Lawyer confirm.
- All purchase guidance is rendered by the deterministic layer. Position as "we check the math in your quote," never "we tell you whether to buy solar."

**Other terms:**
- **Training**: Commercial Terms prohibit Anthropic training on customer content by default (no opt-out needed). Consumer Claude.ai opt-in-training news from 2025 does NOT apply to API.
- **Retention**: API logs default 30 days. **Request Zero Data Retention (ZDR) from Anthropic sales** — PDFs contain names, addresses, utility account numbers.
- **Output ownership**: customer owns; Inputs remain customer's.
- **Indemnification**: Anthropic defends paid-tier customers on third-party IP claims, with carve-outs (customer modifications, customer inputs, trademark, knowing-infringement).
- **Liability cap**: 12 months of fees paid. For a `$0.10-2.00`/user spend, recoverable cap on a hallucination class action is trivial. **Carry independent E&O / tech-liability insurance.**

**Disclaimer on audit output**: still recommended as a general user-transparency + liability posture, not as AUP compliance: *"This analysis is AI-assisted (document extraction). The audit math is computed by deterministic models (pvlib, NREL TMY). Not financial, investment, or tax advice. Consult a licensed solar installer, CPA, or financial advisor before signing a contract."*

**Verdict: Safe on commercial tier with ZDR.** The AUP high-risk-advice clause doesn't reach us under the extraction-only architecture. Don't blur the line by having the LLM generate verdict prose.

### G1b. Google Gemini API (viable alternative / complement to Claude)

**Entry-point matters — use Vertex AI, not AI Studio:**

| Surface | Governing terms | Fit |
|---|---|---|
| **Google AI Studio / Gemini API** (`generativelanguage.googleapis.com`) | [Gemini API Additional Terms](https://ai.google.dev/gemini-api/terms) + [GenAI Prohibited Use Policy](https://policies.google.com/terms/generative-ai/use-policy) | Free tier **prohibited for EEA/UK users** (paid required); paid is commercial-capable but no IP indemnity, no user-configurable ZDR |
| **Vertex AI Gemini** (GCP) | GCP ToS + [GenAI Indemnified Services](https://cloud.google.com/terms/generative-ai-indemnified-services) | **Recommended**: ZDR self-configurable, IP indemnity, data-residency controls, standard DPA |
| **Gemini Apps / consumer Gemini** | Consumer Google ToS | Not for SaaS integration |

**Commercial use**: paid tier on either surface allowed globally; **AI Studio free tier explicitly prohibited for UK/EEA API clients** — we're UK-launching, so free tier is out from day one ([Gemini API Terms](https://ai.google.dev/gemini-api/terms)).

**Pricing (April 2026, per million tokens)** — Gemini is materially cheaper than Claude for PDF extraction:

| Model | Input | Output | ~Cost per 10-page audit |
|---|---|---|---|
| Gemini 2.5 Flash | `$0.30` | `$2.50` | **~`$0.005`** |
| Gemini 3 Flash | `$0.50` | `$3.00` | ~`$0.006` |
| Gemini 3 Pro | `$2.00` | `$12.00` | ~`$0.026` |
| Claude Haiku 4.5 | `$1` | `$5` | ~`$0.012` |
| Claude Sonnet 4.6 | `$3` | `$15` | ~`$0.035` |
| Claude Opus 4.7 | `$15` | `$75` | ~`$0.174` |

Gemini 2.5 Flash ≈ 2.5× cheaper than Haiku 4.5. Batch API is 50% off. Sources: [Gemini API pricing](https://ai.google.dev/pricing), [Vertex GenAI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing).

**Prohibited-use / AUP treatment**: moot for our architecture. [Google's GenAI Prohibited Use Policy](https://policies.google.com/terms/generative-ai/use-policy) touches financial-advice use cases in two places — (a) *deceptive* claims of expertise in finance/legal/medical, (b) *automated decisions with material detrimental impact without human supervision in high-risk domains* — but our LLM role is document extraction only; the audit verdict is computed by deterministic Python. Same reasoning as Anthropic G1. [Gemini API Terms](https://ai.google.dev/gemini-api/terms) still require the standard end-user disclaimer ("don't rely on Services for financial advice…"), which our existing audit-output disclaimer already covers. Lawyer confirm.

**Training on input, retention, and PII exposure (critical per surface):**

| Surface | Training on input? | Default retention | ZDR |
|---|---|---|---|
| AI Studio free tier | **Yes, by default**; human reviewers "may read, annotate, and process" | Unspecified | No |
| AI Studio paid tier | No | "Limited period" for abuse detection; no configurable floor | **No published SKU** |
| **Vertex AI** | No (default for all Gemini foundation models) | Up to 24h cache by default | **Yes** — self-service: disable context caching + request abuse-logging exception |

Because PDFs contain homeowner PII, **only Vertex AI with ZDR meets our bar** (same posture as requesting ZDR from Anthropic). Sources: [Vertex ZDR docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/vertex-ai-zero-data-retention); [Gemini API Terms §Unpaid vs Paid](https://ai.google.dev/gemini-api/terms).

**IP indemnification** ([Google Cloud GenAI Indemnified Services](https://cloud.google.com/terms/generative-ai-indemnified-services)):
- Vertex AI covered by **two-part shield**: training-data claims + output-infringement claims.
- **AI Studio is not covered** — indemnity is Vertex-only.
- Carve-outs (customer-input claims, intentional-infringement, safety-filter-disabled, trademark) parallel Anthropic's Copyright Shield — **lawyer review for exact wording**.
- Low applicability to our use case (we're extracting facts, not generating training-data-reminiscent content), but meaningful delta vs. AI Studio.

**PDF / document input specifics**:
- 1,000 pages / 100 MB max per call ([doc-processing docs](https://ai.google.dev/gemini-api/docs/document-processing), [file-limits blog](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-new-file-limits/)).
- Files API retention is **fixed 48h** — no shorter TTL ([python-genai #1172](https://github.com/googleapis/python-genai/issues/1172)). **Mitigation: send PDFs `inline_data` (<20 MB) so the file never hits the Files API 48h floor.**
- Native PDF ingest is a cost advantage over Claude (Claude's effective PDF page limit is ~100 pages / 32 MB).

**Output ownership**: customer owns Outputs; Google does not claim ownership (parity with Anthropic).

**EU AI Act / UK**:
- We are a deployer, not a GPAI provider — Google holds provider-side obligations. Our deployer duties: transparency disclosure (already covered by our mandatory AI disclaimer), logging, human-oversight framing. Obligations phase in through August 2026.
- Vertex AI supports `europe-west2` (London) for UK data residency — set the region explicitly so UK user PDFs don't default to US inference.

**Verdict: Safe on Vertex AI with ZDR.** AI Studio (even paid) is **not recommended** for production — no IP indemnity, no configurable ZDR, no DPA parity with GCP.

**Recommendation — dual-vendor router, Gemini primary**:
Use **Gemini 2.5 Flash on Vertex AI (ZDR configured)** as the primary extraction model. Keep **Claude Haiku/Sonnet** behind a simple router for (a) retries on low-confidence Gemini outputs, (b) dual-vendor redundancy against outage or pricing shock. The ~2.5× cost saving on the primary path funds the redundancy with margin. Matches the tiered-routing pattern already in PRODUCT_PLAN.md §Cognition Architecture — Gemini tiers replace / parallel the Haiku→Sonnet→Opus ladder. Vendor choice is cost/capability/redundancy driven, not AUP-burden driven, because extraction-only scope puts all three vendors in the same AUP posture.

**Pre-launch action items (Gemini-specific)**:
- Use Vertex AI region `europe-west2` (London) for UK traffic; `us-central1` or `us-east4` for US traffic.
- Configure ZDR: disable context caching + request abuse-logging exception via GCP support.
- Send PDFs via `inline_data` (<20 MB); avoid Files API 48h mandatory retention.
- Execute GCP DPA; add Vertex AI to the `/credits` + privacy-policy subprocessor list.
- Never use AI Studio surface in production (only for dev prototyping with non-PII test fixtures).
- Confirm with counsel: the "automated decisions in high-risk domains without human supervision" clause does not attach to an advisory audit where the homeowner remains the decision-maker.

### G2. Library/dependency licenses

| Library | License | Verdict |
|---|---|---|
| pvlib-python | BSD-3 | **Safe** |
| Next.js | MIT | **Safe** (disable telemetry: `NEXT_TELEMETRY_DISABLED=1`) |
| FastAPI | MIT | **Safe** |
| Alembic | MIT | **Safe** |
| shadcn/ui (+ Radix, Tailwind) | MIT | **Safe** |
| Recharts | MIT | **Safe** |
| TanStack (Query/Router/Table/Form/Virtual) | MIT | **Safe** (TanStack Start has historically had dual-license discussion; verify pins) |
| **Dramatiq** | **LGPL-3** | **Safe with caveat** — pip-import is fine; do not fork; ship LGPL notice. RQ (BSD-2) is the cleaner alternative if you want zero copyleft. |
| RQ | BSD-2 | **Safe** |
| Resend | SaaS commercial | **Safe** (transactional email only; CAN-SPAM/GDPR are your responsibility) |
| Stripe | SaaS commercial | **Safe** — monitor chargebacks; provision reserve; SAQ-A PCI exposure |
| Sentry | SaaS commercial | **Safe** — configure data scrubbing on PDF/report endpoints |
| Plausible | SaaS commercial | **Safe** — EU-hosted, cookie-less |
| PostHog | SaaS commercial | **Safe** — disable session recording on document-upload + report pages |
| **ClamAV** | **GPL-2 (libclamav) / LGPL parts** | **Safe under the daemon pattern** — run as separate `clamd` container, talk over socket. **Never link libclamav into your backend** (would trigger GPL on whole codebase). |

**No AGPL dependencies in the planned stack** — AGPL is the only license that reaches across a network boundary to force SaaS source disclosure. CI step recommended: `pip-licenses` failing the build on AGPL-3.0 / SSPL / Commons Clause in transitive deps.

**LLM-vendor comparison under extraction-only scope:** financial-advice AUP clauses don't attach at any of the three vendors because the Service is used for document parsing, not recommendation generation. Vendor selection is therefore cost + capability + redundancy driven. **Recommended: Gemini 2.5 Flash on Vertex AI (ZDR) as primary PDF extractor — ~2.5× cheaper than Claude Haiku, 1,000-page PDF limit, two-part IP indemnity. Claude Haiku/Sonnet behind a router for retries and dual-vendor redundancy.** OpenAI remains usable but unnecessary given the Gemini + Claude combination.

---

## Section H — Pre-launch action items (consolidated)

> **Phase 1 closed decisions** (cross-ref `PRODUCT_PLAN.md` top section): (1) extract-and-delete PDF retention 24-72h; (2) aggregation default ON, no Phase 1 UI, opt-out plumbing in place — lawful basis Art. 6(1)(f) legitimate interests with documented anonymization (revised; see [ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md), supersedes [ADR 0002](docs/adr/0002-aggregation-default-off.md)); (3) Vertex AI Gemini single-vendor at start (Claude fallback deferred); (4) E&O insurance deferred at Phase 1 launch with calendar trigger before Phase 5 or 50 paid audits/mo. Items below reflect those choices.

### Architecture
- [x] **Extract-and-delete PDF retention** *(closed — Phase 1 decision)*: structured extraction within 24-72h, then purge raw PDF; keep SHA-256 hash + extracted facts + audit output only.
- [ ] **LLM as extractor, not advisor**: deterministic Python computes verdict; LLM outputs are schema-constrained structured data only, never free-form verdict prose. This architectural line is what keeps us outside every LLM vendor's "financial advice / high-risk-domain automation" AUP clause — don't cross it for convenience.
- [ ] **Strip rep PII at extraction**: remove rep direct phone/email; keep company name + license # only.
- [ ] **Per-source attribution columns** on every cached row (TMY, tariff, incentive). Surface in UI and exports.
- [ ] **Place ID storage** for geocoding; never store raw lat/lng beyond 30 days from Google.
- [ ] **ClamAV as sidecar container** (clamd over socket); never link libclamav into backend.
- [ ] **Disable Next.js telemetry**; configure Sentry/PostHog scrubbing on upload/report pages.
- [ ] **Source bucket separation** in cache so a future license change invalidates only one slice.

### Vendor / contract setup
- [x] **LLM vendor setup** *(closed — Phase 1 decision: Vertex AI Gemini single-vendor at start)*: use **Gemini 2.5 Flash on Vertex AI** as primary PDF extractor with ZDR configured (disable context caching + request abuse-logging exception); regions `europe-west2` (UK) + `us-central1`/`us-east4` (US). Send PDFs `inline_data` <20 MB to avoid Files API 48h floor. **Never use AI Studio in production.**
- [ ] **Claude fallback path** *(deferred — re-enable router if extraction quality plateau or vendor-outage exposure justifies)*: design kept warm; if reintroduced, request Anthropic Zero Data Retention before any production traffic.
- [ ] **Execute GCP DPA**; add Vertex AI to privacy-policy subprocessor list. (Anthropic DPA only when Claude fallback is reintroduced.)
- [ ] **Sign UtilityAPI** (US) and **n3rgy enterprise** (UK) as aggregators; model `$3`/customer/month into Tracker pricing.
- [ ] **Defer DSIRE subscription** until counsel reviews ShareAlike implications; consider primary-source state-incentive curation instead.
- [ ] **Defer Google Solar API** (already in plan); use user-entered shading + PVWatts.
- [ ] **Defer SolarEdge ISV partnership**; launch with site-owner-key model + ISV pursued in parallel.
- [ ] **Defer Tesla Fleet API**; consider supporting Tesla via customer-supplied CSV at launch.
- [ ] **Skip Met Office DataHub, Solcast, Meteonorm** for MVP — covered free by PVGIS/CAMS/ERA5/NSRDB.
- [ ] **Skip MCS Installations Database** for UK benchmarks; seed from user uploads only.

### Legal / compliance
- [ ] **AI-assistance + not-financial-advice disclaimer** on every audit report and exported PDF (general transparency / liability posture; not AUP-mandatory under extraction-only architecture).
- [x] **Privacy policy + ToS** *(aggregation default closed — Phase 1 decision: default ON with no UI surface, opt-out plumbing in place; lawful basis Art. 6(1)(f); see [ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md))*: user warrants right to share proposal; privacy policy describes default-ON aggregation explicitly with the opt-out path; data-deletion mechanism for raw PDF + PII vault.
- [ ] **GDPR DPA + Art. 6 lawful-basis documentation** for installer-rep data and smart-meter data.
- [ ] **DPIA before reviving** named-installer or named-rep public analytics.
- [ ] **E&O / tech-liability insurance** *(deferred — Phase 1 decision)*: not bound at MVP launch. Calendar trigger to bind a policy: before Phase 5 public-launch push, or at 50 paid audits/month, whichever first. AI-assistance + not-financial-advice disclaimer on every audit report from day 1 (independent of insurance status).
- [ ] **`/credits` page** listing every MIT/BSD/LGPL notice + every CC-BY/CC-BY-SA/OGL/Copernicus attribution string.
- [ ] **Logo / endorsement guardrails**: never use NREL/DOE/LBNL/NWS/MCS/Met Office logos or imply endorsement.

### Pricing / unit-economics consequences
- UtilityAPI `$3`/meter/month consumes ~33% of `$9` Tracker ARPU — confirm gross-margin model still works (Tracker phase, not Phase 1).
- LLM spend per audit on Vertex AI Gemini 2.5 Flash: realistic ~`$0.005-0.05` per 10-page audit; budget cap ≤`$2` retained as a runaway-detection trigger, not as the expected operating point. Single-vendor posture removes Anthropic ZDR overhead from Phase 1 cost stack.
- Solcast / Meteonorm / Met Office paid tiers all break MVP unit economics; stick to free sources.
- Enphase commercial-tier API: `~$80/mo` base + per-system surcharge; budget into Tracker COGS (Tracker phase, not Phase 1).

---

## Section I — Open questions for outside counsel

1. **DSIRE CC-BY-SA contamination boundary**: at what level of integration does ShareAlike attach to our incentive tables? Is "display with attribution and link to license" sufficient to keep our proprietary curated DB outside the copyleft scope?
2. **Extraction-only scope vs. LLM vendor AUPs** — confirm our reading that Anthropic's High-Risk "investment advice / financial eligibility" clause, Google's "automated decisions in high-risk domains" clause, and OpenAI's "personalized professional advice" clause all target what the Service produces (recommendations/decisions), and therefore do not attach when the LLM only extracts structured fields and a deterministic engine computes the audit. Edge case to pressure-test: LLM-generated flags and ask-your-installer questions grounded in deterministic counterfactual values (PRODUCT_PLAN.md §Cognition Architecture) — are those still "extraction/explanation" or do they cross into "advice"?
3. **Aggregation default ON, lawful basis Art. 6(1)(f) legitimate interests** ([ADR 0005](docs/adr/0005-aggregation-default-on-no-ui.md), supersedes [ADR 0002](docs/adr/0002-aggregation-default-off.md)) — confirm the LIA holds under UK ICO scrutiny given the anonymization design (ZIP-3/postcode-district bucketing, no homeowner identifiers, rep contact PII stripped, k-anonymity gate at publish). If UK ICO posture is hostile to default-ON, options: per-region default flag (US default-ON, UK default-OFF) or UK-specific consent prompt while keeping US default-ON. Mandatory pre-Phase-3b counsel review.
4. **Sales-rep PII lawful basis**: legitimate-interest defensibility for retaining individual rep names + license #s in our installer DB (internal-only, pre-public-disclosure threshold). Required DPIA structure.
5. **Installer "no-share" / confidentiality footers**: confirm our position that footer declarations don't bind a homeowner who never signed; confirm we have no tortious-interference exposure absent specific-contract knowledge.
6. **Named-installer disclosure threshold** (currently N≥20 in plan): is N=20 + right-to-respond enough to defend defamation/trade-libel? What jurisdictions are highest-risk?
7. **CEC equipment list redistribution**: does using the CEC PV/Storage list as our internal equipment-DB seed (with attribution) qualify as Public Records Act use, or does the CEC "no commercial use" ToS override?
8. **MCS Installations Database**: is per-individual-user lookup (the user looks up *their own* installation) defensible as a customer-agent action, separate from bulk reuse?
9. **UtilityAPI M&A auto-termination clause**: should we hedge with a secondary aggregator (Arcadia / direct CMD) given how disruptive a single-vendor termination would be?
10. **Wood Mackenzie / SEIA SMI exec-summary citations** in landing-page marketing copy — confirm "verbatim attribution string + no chart reproduction" is the safe envelope.

---

## Appendix — Source inventory cross-reference

Quick lookup: every external source mentioned in `VISION.md` or `PRODUCT_PLAN.md`, mapped to its section in this document.

| Source | Section | Verdict |
|---|---|---|
| NREL TMY / NSRDB / PSM3 | A | Safe |
| pvlib | A, G | Safe (BSD-3) |
| OpenEI URDB | A, C | Safe (CC0) |
| ResStock / DOE | A | Safe (CC BY 4.0) |
| Green Button | A, C | Use aggregator at launch |
| DSIRE | A, C | **Lawyer review** (CC-BY-SA copyleft) |
| LBNL studies / Tracking the Sun | A, F | Safe (dataset CC-BY); cite, don't lift PDF figures |
| PVGIS | B | Safe (CC BY 4.0) |
| ERA5 / Copernicus CDS | B | Safe |
| CAMS Solar Radiation | B | Safe |
| Open-Meteo | B | Needs paid tier |
| NOAA | B | Safe (US PD) |
| Met Office | B | Skip MVP |
| Solcast | B | Avoid |
| Meteonorm | B | Avoid for MVP |
| UtilityAPI | C | Safe; budget `$3`/meter/mo |
| Octopus Energy API | C | Safe per-customer |
| Hildebrand / n3rgy | C | Paid + GDPR review |
| Ofgem | C | Safe (OGL v3) |
| CPUC ACC (NEM 3.0) | C | Safe (numeric values only) |
| CEC equipment lists | C | Lawyer review for heavy use |
| SREC markets | C | Avoid proprietary indices |
| MCS Installations DB | C | Lawyer review + paid agreement |
| Enphase | D | Safe (lawyer review for installer-benchmarking) |
| SolarEdge | D | Workable / needs ISV long-term |
| Tesla Fleet API | D | Defer to v2 |
| GivEnergy | D | Safe |
| Solis | D | Safe with caveats |
| Growatt | D | Avoid at launch |
| Google Solar API | E | Avoid |
| Project Sunroof | E | Avoid as data source |
| Google Geocoding | E | Paid; use Place ID |
| Zillow / Bridge | E | Avoid |
| Redfin | E | Lawyer review for live use; cite-only safe |
| Mapbox | E | Paid tier |
| OSM / Microsoft Footprints | E | Safe (ODbL with attribution) |
| USGS 3DEP / UK EA LIDAR | E | Safe |
| EnergySage / SolarReviews / Solar.com | F | Limited scrape risk; avoid calculator/quote scraping |
| OpenSolar / Aurora / HelioScope | F | Only user-uploaded PDFs |
| Reddit | F | Avoid automated ingestion |
| MSE / Which? | F | Go upstream |
| Wood Mac residential-PV | F | Avoid unless licensed |
| SEIA / Wood Mac SMI | F | Exec summary only with attribution |
| User installer PDFs | F | Extract-and-delete; transformative fair use |
| Anthropic Claude API | G | Disclaimer + architectural mitigation |
| **Google Gemini (Vertex AI)** | **G** | **Safe with ZDR; recommended primary for PDF extraction (most permissive AUP + cheapest)** |
| Google Gemini (AI Studio) | G | Not for production — no IP indemnity, no user-configurable ZDR, EEA/UK free-tier prohibited |
| OpenAI API | G | Stricter than Anthropic on advice |
| MIT/BSD libs (Next/FastAPI/shadcn/Recharts/TanStack/etc.) | G | Safe |
| Dramatiq | G | LGPL — safe via pip; or use RQ |
| ClamAV | G | Safe via daemon; never link libclamav |
| Resend / Stripe / Sentry / Plausible / PostHog | G | Safe with config hardening |
