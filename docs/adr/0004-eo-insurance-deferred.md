# 0004. E&O insurance deferred at Phase 1 launch

**Decision**: Errors & Omissions / tech-liability insurance is not bound for the Phase 1 MVP launch. A calendar trigger binds a policy before Phase 5 public-launch push, or at 50 paid audits/month, whichever first.

**Status**: accepted

**Date**: 2026-04-22

## Context

E&O for software that informs a $25k+ purchase is appropriate at scale (~$100-250/mo). At Phase 1 MVP volume (closed beta, founders bundle, < 50 paid audits/mo expected) the policy cost outruns the realistic exposure, especially under our extraction-only architecture (LLM extracts; deterministic Python computes; user retains decision).

The disclaimer (AI-assist + not-financial-advice) is unconditional — it ships from day 1 regardless of insurance status. The disclaimer is general transparency / liability posture; it is not AUP-mandatory under extraction-only scope.

## Decision

Defer policy binding. Calendar gate: bind before Phase 5 public-launch push, or at 50 paid audits/month, whichever first.

## Consequences

**Enables**: lower fixed cost during MVP; runway preserved for engineering investment.

**Constrains**: any incident before binding falls to founder personal exposure modulo Anthropic / Vertex IP indemnity (limited applicability under extraction-only). The 50-audits/mo trigger is the hard cap on this exposure window.

**Trigger to revisit**: 50 paid audits/month milestone; OR Phase 5 public-launch readiness; OR any cease-and-desist or installer pushback that materially changes the risk profile.

## Implementation

- Bead `chart-solar-6s7` — AI-assist + not-financial-advice disclaimer on every audit/export (ships from day 1)
- E&O policy binding tracked in operational runbook outside beads (founder/legal track)

## References

- `PRODUCT_PLAN.md` § Phase 1 closed decisions, decision (4)
- `BUSINESS_PLAN.md` § Risks (insurance + E&O exposure rows)
- `LEGAL_CONSIDERATIONS.md` § H (calendar trigger)
