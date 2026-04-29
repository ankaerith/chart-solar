# 0002. Aggregation opt-in default OFF

**Decision**: After every audit, we ask the user whether to contribute anonymized pricing to the regional benchmark DB. The toggle defaults to OFF. Nothing is added to `region_pricing_aggregates` without explicit consent.

**Status**: accepted

**Date**: 2026-04-22

## Context

The regional pricing DB is the product's long-term moat — but UK ICO interpretation increasingly treats pre-ticked consent as invalid, and CCPA post-CPRA tightens the same way. A default-ON aggregation would be faster N-ramp and weaker lawful basis. Default-OFF is the inverse.

## Decision

Default OFF. Post-audit prompt with clear copy on what is and isn't shared. Reversible.

## Consequences

**Enables**: clean Art. 6 consent posture under both UK GDPR and CCPA; high-trust framing in privacy policy.

**Constrains**: slower N-ramp on regional aggregates → "Median $/W in your ZIP" copy can't credibly anchor the landing page in the first 6-12 months. Mitigation: post-audit copy that earns opt-in; rely on opt-in conversion rate as a brand-trust KPI.

**Trigger to revisit**: opt-in rate below 30% sustained → consider in-product framing changes or, post-counsel-review, a default-ON variant for non-EU users (forks the data flow).

## Implementation

- Bead `chart-solar-fc1` — Post-audit aggregation opt-in flow (default OFF)
- Bead `chart-solar-l5h8` — Opt-in default-OFF aggregation test
- Schema: `installer_quotes.aggregation_opt_in BOOLEAN DEFAULT FALSE`

## References

- `PRODUCT_PLAN.md` § Phase 1 closed decisions, decision (2)
- `BUSINESS_PLAN.md` § Red-team #2 (slower N-ramp trade-off)
- `LEGAL_CONSIDERATIONS.md` § I.3 (open question)
