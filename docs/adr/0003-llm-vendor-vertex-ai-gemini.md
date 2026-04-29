# 0003. LLM vendor: Vertex AI Gemini, single-vendor at start

**Decision**: Gemini 2.5 Flash on Vertex AI is the primary PDF extraction model. ZDR configured (context caching disabled, abuse-logging exception requested). Regions pinned: `europe-west2` (UK), `us-central1`/`us-east4` (US). Claude fallback router design retained but deferred.

**Status**: accepted

**Date**: 2026-04-22

## Context

Phase 1 LLM choice has three axes: cost, capability, redundancy. AI Studio (consumer-style endpoint) is excluded — no IP indemnity, no configurable ZDR, EEA/UK free-tier prohibited. That leaves Vertex AI Gemini and Anthropic Claude.

Gemini 2.5 Flash on Vertex AI is ~2.5× cheaper than Claude Haiku for 10-page audits, supports 1,000-page PDF inputs (vs Claude's ~100), has two-part IP indemnity on the Vertex SKU, and ZDR is self-configurable. Single-vendor is operationally simpler: one DPA, one ZDR posture, one billing surface.

Pure ZFC framing also reduces vendor coupling: the model only extracts structured fields; deterministic Python computes the audit verdict. Vendor switching is a wrapper change, not a logic change.

## Decision

Vertex AI Gemini single-vendor at start. Claude fallback router design kept warm but not implemented; reintroduce when extraction quality plateaus or vendor-outage exposure justifies the second integration.

## Consequences

**Enables**: lower per-audit cost, simpler ops, larger PDF support, indemnity coverage on the Vertex SKU.

**Constrains**: single point of failure on extraction quality + availability; pricing-shock risk from a single vendor. AI Studio is explicitly **never** used in production — only Vertex.

**Trigger to revisit**: extraction accuracy plateau on the labeled set; Vertex pricing change; or an outage event materially affecting paid-audit SLA.

## Implementation

- Bead `chart-solar-5e1` — Vertex AI client wrapper (region pinning, ZDR, inline PDF)
- Bead `chart-solar-1yz` — Tiered routing (Pattern B: deterministic floor + model opinion)
- Bead `chart-solar-bko` — Vertex AI server-side context caching for stable prefixes
- Bead `chart-solar-p6vp` — In-code DPA-acceptance gate

## References

- `PRODUCT_PLAN.md` § Phase 1 closed decisions, decision (3); § Cognition Architecture
- `LEGAL_CONSIDERATIONS.md` § G1b (Gemini API analysis)
