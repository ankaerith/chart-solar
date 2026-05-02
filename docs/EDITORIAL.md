# Editorial style guide — Field Notes

Voice + house rules for [`/notes/*`](../frontend/content/notes/) — the editorial section. Keep this short. If a rule isn't here, default to the [`VISION.md`](../VISION.md) framing: *Consumer Reports with an NPV engine.*

## Voice

- **Planner-nerd, regulator-friendly.** Direct, declarative, with receipts. We are the over-researcher's analyst, not their cheerleader.
- **Named practices, never named companies.** "A 22% dealer-fee markup" — fine. "[Installer X]'s 22% dealer-fee markup" — not fine. Same applies to lenders and monitoring vendors. Public 10-K disclosures are a partial exception (cite the doc, not the brand) when the source is the disclosure itself.
- **No affiliate framing, ever.** No referral copy. No "schedule a consultation" CTA that hands the reader to anyone. The product is the trust signal; the article is the proof.
- **Treat readers as smart.** Show your math. If a claim has a Monte Carlo behind it, say so and link the methodology.

## Headlines

- **Declarative beats clever.** *"NEM 3.0 didn't kill solar in California. It killed solar without batteries."* > *"The truth about NEM 3.0."*
- **Numbers in the dek when they exist.** *"We audited 312 proposals. Median first-year overstatement: 8.4%."* The number does the persuading.
- **One-sentence headline, one-sentence dek.** Both can wrap; neither should run on.
- **Sentence case. Periods at the end.** Editorial weight comes from the typography (Newsreader serif), not from caps.

## Citations

- **Numbered footer block** (`Cited in this piece`) — see [`design/solar-decisions/project/screen-notes.jsx:419–436`](../design/solar-decisions/project/screen-notes.jsx). Each item: source, year, locator (page / section / dataset name).
- **Prefer primary sources.** NREL, CFPB, Ofgem, CPUC, FERC, 10-Ks, dataset DOIs. Aggregators only when the primary isn't reachable.
- **Internal corpus is allowed and labeled.** *"Solar Decisions internal audit corpus, 2024–2026 (n=312, CO/CA/TX/AZ/MA/NJ)"* is a legitimate citation; we own it. Disclose sample size and geography.
- **Link out where the license permits.** Don't paywall-launder.

## Methodology disclosure

- Every analytical claim ships its inputs in the body or links a methodology doc. Inputs that need disclosing: simulation count, time horizon, discount rate, escalator distribution, weather source, cohort filters.
- Numerical results carry uncertainty: prefer *"median +$31,400 (P10 +$8,200 / P90 +$58,700)"* over a single point estimate.
- If a claim depends on a chart, the chart's data + parameters live in the article frontmatter, not in a hidden script.

## AI-assist disclosure

Every published article must include the AI-assist + not-financial-advice disclaimer in the footer (per [`docs/ENGINEERING.md`](ENGINEERING.md) Definition of Done). The disclaimer template:

> Research, drafting, and chart generation in this article were AI-assisted. Methodology and conclusions were reviewed by a human author. This is journalism, not financial advice.

Disclosure goes below the citations block, above the related-articles strip. Do not bury it; do not embellish it.

## Bylines

Field Notes does not display human bylines for v1 — this is a deliberate product decision (see [`bd show chart-solar-r6sy.1`](#beads)). JSON-LD `Article.author` is wired to the Chart Solar `Organization`. When a real author is added later, this rule supersedes; until then no fictional bylines.

## Format

- **MDX**, in [`frontend/content/notes/`](../frontend/content/notes/). One file per article. Filename = slug.
- **Frontmatter contract** (enforced at build by Zod):
  ```yaml
  ---
  title: ...
  dek: ...
  date: 2026-03-18           # ISO date, the publication date
  readTime: 11               # minutes, integer
  category: Capital | Tariffs | Audit | Methodology | Track | Analysis
  tag: Methodology | Analysis | Audit
  featureArt: dealer-fees    # references components/notes/illustrations/dealer-fees.tsx
  citations: [...]           # array of { source, year, locator }
  ---
  ```
- **Drop cap, blockquote, embedded illustration** — see [`design/solar-decisions/project/screen-notes.jsx:NoteArticle`](../design/solar-decisions/project/screen-notes.jsx) for the visual contract. Don't reinvent the layout per article.
- **Body width**: 680px. Hero + citations: 760px. Don't widen for "long tables" — break the table out as a separate illustration component.

## Tone reference

The three featured pieces in the design mock are the templates. Read them when in doubt:

- [`design/solar-decisions/project/screen-notes.jsx`](../design/solar-decisions/project/screen-notes.jsx) — `dealer-fees`, `nem3`, `overstating` notes (lines 4–71 carry the title + dek; lines 219–286 carry the illustrations; lines 305–438 carry a sample article body).

Prefer the `dealer-fees` body as the canonical voice example: a homeowner anecdote in lede, mechanism explained with concrete numbers, blockquote that lands the punchline, dataset-grounded close.

## Cadence

The mock targets *"new entries every two weeks"*. That's aspirational. Ship when the math is solid; an empty grid beats a thin piece. Below 6 published notes the index renders short — that's fine.

## Beads

- [`chart-solar-r6sy`](#) — Field Notes epic.
- [`chart-solar-r6sy.1`](#) — Organization-as-author JSON-LD wiring.
- [`chart-solar-r6sy.2`](#) — Editorial illustration component system.
- [`chart-solar-r6sy.3`](#) — Cross-product note linking.
- [`chart-solar-r6sy.4`](#) — This file.
