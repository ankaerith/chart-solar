<!-- One sentence: what changed, why, and the bead this closes. -->

Closes `chart-solar-…`

## Summary

<!-- 2-4 bullets, what's in the diff. Skip the stuff a reviewer can see. -->

## Definition of Done

- [ ] Tests added or updated; `uv run pytest` and `pnpm test` pass locally
- [ ] `pnpm typecheck`, `pnpm lint`, `ruff check`, `mypy --strict` pass
- [ ] Engine changes: golden fixture passes within tolerance; pvlib version pinned in snapshot
- [ ] UI changes: keyboard nav + focus rings + axe-clean (Tier 1+2 routes)
- [ ] DB schema changes: Alembic migration; reversible; no destructive op without ADR
- [ ] External-API changes: respects retry/backoff util; no synchronous HTTP from API thread
- [ ] PII / user-scoped data: passes through `require_owner`; row-level access enforced at API layer
- [ ] License-relevant additions: `pip-licenses` clean (no AGPL/SSPL/Commons Clause); attribution added to `/credits` if new data source
- [ ] LLM prompt changes: prompt version bumped; snapshot pinned; eval-set delta noted (post-MVP)
- [ ] User-facing copy: matches voice ("named practices, never named companies"); disclaimer present where required (`docs/EDITORIAL.md`)
- [ ] UI changes: design ref on the bead points to the implemented mock (`design/solar-decisions/project/*.jsx`); deviations called out in the PR body
- [ ] Bead acceptance criteria each addressed in this PR or a linked follow-up bead

## ADR

<!-- Did this introduce or supersede an architecture decision? Link/draft an ADR in docs/adr/. -->

- [ ] No architectural decision in this PR
- [ ] New ADR: `docs/adr/NNNN-…` drafted
- [ ] Supersedes ADR `NNNN`

## Verification

<!-- How did you exercise this? Screenshots/curls/test output. UI work: actually opened a browser. -->
