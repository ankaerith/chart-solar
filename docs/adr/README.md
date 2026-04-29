# Architecture Decision Records

Short, append-only log of architectural decisions: what was decided, when, and why. Future readers (humans + agents) can trace the reasoning without re-deriving it from scattered chat logs and PRs.

## When to write one

Write an ADR when a decision:
- Has multiple plausible options
- Will be expensive to reverse
- Will surprise a future reader who doesn't know the history
- Cuts across multiple modules or phases

Skip ADRs for: choice of variable name, library version bumps, anything obvious from code.

## Format

Use [`template.md`](./template.md). Keep ADRs short — one screen if possible. Status is `proposed`, `accepted`, `superseded by NNNN`, or `rejected`. Numbering is monotonic.

Don't edit accepted ADRs in place — supersede with a new one and link both directions.

## Index

| # | Title | Status |
|---|---|---|
| [0001](./0001-pdf-retention-extract-and-delete.md) | PDF retention: extract-and-delete within 24-72h | accepted |
| [0002](./0002-aggregation-default-off.md) | Aggregation opt-in default OFF | superseded by [0005](./0005-aggregation-default-on-no-ui.md) |
| [0003](./0003-llm-vendor-vertex-ai-gemini.md) | LLM vendor: Vertex AI Gemini, single-vendor at start | accepted |
| [0004](./0004-eo-insurance-deferred.md) | E&O insurance deferred at Phase 1 launch | accepted |
| [0005](./0005-aggregation-default-on-no-ui.md) | Aggregation default ON, no Phase 1 UI, opt-out plumbing in place | accepted |

## Conventions

- Filename: `NNNN-kebab-case-title.md`
- Open with a one-sentence decision in **bold**.
- Always include **Context**, **Decision**, **Consequences** sections.
- Link the source documents (`VISION.md`, `PRODUCT_PLAN.md`, `LEGAL_CONSIDERATIONS.md`) and any beads that implement the decision.
