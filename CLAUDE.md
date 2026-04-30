# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->


## Quality gates

Before committing backend changes, run all four gates locally — CI runs the same set and `ruff format --check` is easy to miss because `ruff check` doesn't cover formatting:

```bash
uv run ruff check backend/         # lint
uv run ruff format --check backend/  # formatting (separate from lint!)
uv run mypy backend/               # strict types
uv run pytest --cov                # tests + coverage gate
```

If `ruff format --check` flags anything, run `uv run ruff format backend/` to fix in place. Do not push without all four gates green.

For the frontend, the equivalents are `bun run lint`, `bun run typecheck`, `bun run build`.

## Where to find things

- **Strategy**: [`VISION.md`](VISION.md) — wins on conflicts.
- **Engineering spec**: [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md) — features, architecture, phased roadmap, verification.
- **Legal**: [`LEGAL_CONSIDERATIONS.md`](LEGAL_CONSIDERATIONS.md) — data sources, IP, AUP, retention.
- **Engineering practices**: [`docs/ENGINEERING.md`](docs/ENGINEERING.md) — Definition of Done, repo layout, testing, ops.
- **Secret management**: [`docs/SECRETS.md`](docs/SECRETS.md) — env vars, rotation cadence, deploy targets.
- **Architecture decisions**: [`docs/adr/`](docs/adr/) — read the index in `README.md`. Don't edit accepted ADRs in place; supersede.
- **PR checklist**: [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md).
- **Tasks + memory**: `bd ready`, `bd show <id>`, `bd memories <keyword>`.

## Beads conventions

- **Validation**: `validation.on-create=warn` — bd warns on missing fields but doesn't block creation.
- **Labels**: every issue gets a `phase:*` (one of `phase:0`, `phase:1a`, `phase:1b`, `phase:2`, `phase:3a`, `phase:3b`, `phase:4`, `phase:5`) and an `area:*` (`area:engine`, `area:data`, `area:ui`, `area:ops`, `area:legal`, `area:pdf`, `area:qa`). `bd label list-all` shows current usage.
- **Hooks**: pre-commit + pre-push run `bd hooks run …` (export JSONL + dolt sync). The pre-commit framework's `.pre-commit-config.yaml` invokes the same beads hook so they coexist with ruff / mypy / eslint / gitleaks / pip-licenses.

## Architecture in one paragraph

FastAPI (Python) backend, Next.js 16 (App Router, React 19) frontend, Postgres for state, Redis + RQ for the forecast queue, pvlib for production physics, Vertex AI Gemini for PDF extraction (Phase 1b). Deployed as containers; specific host is undecided and the stack stays portable — no provider-proprietary features in the hot path.

## Engine layout

`backend/engine/pipeline.py` composes `backend/engine/steps/*.py`. Each step is a pure `(state) -> state` transform that registers itself under a feature key. `backend/engine/registry.py` decides which steps run for a given tier.

## ZFC (Zero-Framework Cognition)

Application code is a thin, deterministic shell. Cognition belongs to models. **Anti-patterns to refuse:**

- Regex / pattern matching of semantic fields (installer names, equipment, $/W).
- Per-installer template fingerprinting in app code.
- Hard-coded flag taxonomies.
- Keyword-based document classification.
- Fallback heuristics that encode domain knowledge.

If you find yourself writing one of these, stop. Use a model with structured output instead, and put the structured-output schema at the IO boundary as a Pydantic / TS type.

Pure math (pvlib, NPV, IRR, amortization, tariff arithmetic) stays deterministic in Python. That's not cognition; that's physics + accounting.

## Stack rules

- No Vercel-specific features (Edge runtime, KV, Blob, ISR-specific semantics, Vercel Cron).
- No Supabase RLS coupling, no Supabase Edge Functions. Postgres via portable SQL only.
- Auth: Auth.js (NextAuth) on Postgres or FastAPI-native magic-link JWT — both portable.
- Object storage: S3-compatible (R2, S3, GCS) — same SDK code.
- **Frontend package manager: bun.** Use `bun install` / `bun run` / `bun.lock`. Don't propose npm, yarn, or pnpm.
- Backend: Python 3.12, managed with **uv** (`uv sync`, `uv run`). Don't propose pip/poetry/pipenv.
