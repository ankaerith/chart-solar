# 0001. PDF retention: extract-and-delete within 24-72h

**Decision**: Raw installer-PDF uploads are auto-purged from object storage within 24-72 hours of upload. We retain only (a) SHA-256 hash for dedupe, (b) extracted JSON (per the field inventory), (c) audit output.

**Status**: accepted

**Date**: 2026-04-22

## Context

Installer proposals are copyrightable user-uploaded content containing significant homeowner PII (name, address, signature, utility-account #) and sales-rep PII (name, phone, email). Long-term retention compounds copyright risk (Authors Guild / Thomson Reuters v. ROSS) with GDPR/CCPA exposure and breach radius.

Three options were weighed (LEGAL_CONSIDERATIONS.md §F1 retention table):
1. Indefinite — highest legal + breach risk
2. 30-90 day — moderate on both axes
3. **Extract + delete within 24-72h** — minimal on both axes

## Decision

Option 3. After successful structured extraction, the raw PDF is purged from object storage by a TTL job. The `installer_quotes` row keeps SHA-256 hash + extracted JSON + audit output + `raw_pdf_purged_at` timestamp.

## Consequences

**Enables**: clean fair-use posture (transformative analysis, not retention); minimal PII breach radius; GDPR-compliant by design.

**Constrains**: re-extraction with a better model is impossible without re-upload; user mis-uploads must be caught within the TTL window.

**Trigger to revisit**: GDPR review pushes shorter; or user-experience friction on mis-upload correction warrants user-extend.

## Implementation

- Bead `chart-solar-ebo` — PDF TTL purge job writes `raw_pdf_purged_at`
- Bead `chart-solar-98cd` — Automated PDF TTL purge test
- Schema: `installer_quotes.raw_pdf_purged_at`, `installer_quotes.raw_pdf_sha256`

## References

- `PRODUCT_PLAN.md` § Phase 1 closed decisions, decision (1)
- `LEGAL_CONSIDERATIONS.md` § F1 (Installer proposal PDFs), § H Architecture
