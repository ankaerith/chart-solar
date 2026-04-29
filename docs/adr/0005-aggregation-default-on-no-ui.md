# 0005. Aggregation default ON, no Phase 1 UI, opt-out plumbing in place

**Decision**: Aggregation contribution to `region_pricing_aggregates` defaults to ON. The contribution toggle is **not exposed** in the Phase 1 UI. The opt-out code path (data model + API + cascade) lands from day 1 so a future settings page can surface the control without a schema migration.

**Status**: accepted

**Date**: 2026-04-28

**Supersedes**: [0002](./0002-aggregation-default-off.md)

## Context

ADR 0002 chose default-OFF + visible toggle to optimize for clean Art. 6(1)(a) consent under UK GDPR. The trade-off it accepted: the regional benchmark moat takes 6-12 months to compound at realistic launch volumes, weakening the launch-narrative anchor ("median $/W in your ZIP") for the first year — which is exactly the window where SEO content needs the data.

Product call (founder/PM): prioritize moat-compounding velocity at the legal cost of pivoting the lawful basis from **Art. 6(1)(a) consent** → **Art. 6(1)(f) legitimate interests**. Hide the toggle in Phase 1 (no surface area, no copy decisions, no opt-in friction); revisit visible UI when the rest of the product is mature enough that the surface is worth the design cost.

## Decision

1. **Default ON.** New audits write `installer_quotes.aggregation_opt_in = true` on insert. The DB column DEFAULT is `TRUE`.
2. **No Phase 1 UI.** No post-audit consent prompt, no settings toggle, no banner. Privacy policy + ToS describe the default-ON aggregation explicitly so users have notice.
3. **Opt-out plumbing lands now.** A `users.aggregation_opt_out` boolean column exists from day 1; an authenticated `PATCH /api/me/aggregation` endpoint flips it; flipping it cascades to mark all of the user's existing `installer_quotes.aggregation_opt_in = false`. The next aggregate refresh excludes them.
4. **Future UI is a separate bead.** When the settings page lands, surfacing the control is a one-screen change — no schema or service work.

## Consequences

**Enables**: faster moat compounding from day 1; "median $/W in your ZIP" copy is credible at launch in higher-volume metros; aggregation flow has zero conversion cost (no copy to write, no funnel step that drops users).

**Constrains**:
- Lawful basis pivots to Art. 6(1)(f) legitimate interests — requires a documented Legitimate Interest Assessment (LIA). Anonymization is load-bearing: only `location_bucket` (ZIP-3 / postcode district), `system_spec`, `financials`, `quoted_metrics` flow to aggregates; no homeowner identifiers; sales-rep direct contact PII already stripped per `chart-solar-00s`; k-anonymity gate (`chart-solar-5ww`) before any aggregate publishes.
- **UK risk flag**: ICO interprets Art. 6(1)(f) tightly. Default-ON aggregation under UK GDPR is the case most likely to draw scrutiny. Before Phase 3b (UK launch) we revisit — options include per-region default (US default-ON, UK default-OFF) or a UK-specific consent prompt while keeping US default-ON.
- Privacy-policy + ToS copy must be unambiguous about default-ON behavior and the opt-out path. Not an engineering task, but the privacy-policy bead closes are gated on this language being settled.
- Without a visible toggle, users who care about contribution status learn it only by reading the privacy policy. That's acceptable for a niche product; mass-market would not be.

**Trigger to revisit**:
- Counsel review for UK launch (Phase 3b) — most likely trigger.
- ICO / state-AG inquiry, or a sustained pattern of user complaints about contribution status.
- Phase 5 public launch — re-examine whether the toggle should surface as the product matures.

## Implementation

- Bead `chart-solar-fc1` — re-scoped to "default-ON aggregation + opt-out plumbing, no Phase 1 UI"
- Bead `chart-solar-l5h8` — re-scoped to verify default-ON + opt-out path
- Bead (new) — User-facing aggregation toggle in /settings (deferred)
- Schema changes:
  - `installer_quotes.aggregation_opt_in BOOLEAN NOT NULL DEFAULT TRUE` (was DEFAULT FALSE)
  - `users.aggregation_opt_out BOOLEAN NOT NULL DEFAULT FALSE` (new)
- Aggregate query: `WHERE installer_quotes.aggregation_opt_in = TRUE` (per-quote authoritative; per-user opt-out cascades to per-quote)

## References

- [`0002-aggregation-default-off.md`](./0002-aggregation-default-off.md) — superseded
- `PRODUCT_PLAN.md` § Phase 1 closed decisions, decision (2)
- `LEGAL_CONSIDERATIONS.md` § F1 (privacy architecture), § H, § I.3
- `BUSINESS_PLAN.md` § Risks, § Red-team
