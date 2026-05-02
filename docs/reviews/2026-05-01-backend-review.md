# Backend code review — 2026-05-01

Multi-lens review of `backend/` (Python, ~22.6k LOC across 173 files): security,
code quality, architecture, test suite, performance/async. Each lens was a
separate reviewer; findings below are the de-duplicated triage.

Filed beads issues are linked inline. "Acknowledged, not filed" entries are
either tracked elsewhere, defended in code, or explicitly declined as
over-engineering.

## Filed beads issues (this review)

Auth + payments (parented under `chart-solar-bcy`):
- `chart-solar-wk0a` P1 — Magic-link CSRF + token-leak vector
- `chart-solar-e543` P1 — Stripe webhook trusts unvalidated `metadata.user_id`
- `chart-solar-6jre` P1 — Rate limiting on auth endpoints
- `chart-solar-xoej` P1 — Wire `current_tier()` to `tier_for_user()`
- `chart-solar-3cny` P2 — Send Resend email outside DB session block
- `chart-solar-f4he` P2 — Drop emails from auth structured logs

Engine + workers (parented under `chart-solar-f9l`):
- `chart-solar-enow` P2 — Sync redis enqueue blocks event loop
- `chart-solar-9271` P3 — Split `db/tmy_cache.py`
- `chart-solar-z1po` P3 — Engine pipeline registry consolidation
- `chart-solar-n992` P3 — Drop `apply()` methods on regime configs
- `chart-solar-pvec` P3 — Memoize TOU period scan in `_bill_tou`

Cross-cutting / engineering excellence (parented under `chart-solar-sonm`):
- `chart-solar-3ix1` P1 — `canonical_request_hash` int/float collision
- `chart-solar-azc2` P1 — `claim_idempotency_slot` race fallback
- `chart-solar-qwno` P2 — Reuse `httpx.AsyncClient` per service
- `chart-solar-3u28` P2 — Test-coverage cluster (6 modules)
- `chart-solar-ecf3` P2 — Add `db -/-> providers` and `infra -/-> db` lint-imports contracts
- `chart-solar-a7gp` P2 — `@idempotent` decorator SELECT-then-INSERT race
- `chart-solar-pi6n` P2 — `get_job` swallows every exception
- `chart-solar-oopc` P2 — Cap request body size on `/api/forecast` + `/api/stripe-webhook`
- `chart-solar-prs4` P3 — `BaseHTTPMiddleware` → pure ASGI
- `chart-solar-tomu` P3 — Test-suite scaffolding cleanup

Standalone (no natural epic):
- `chart-solar-54n9` P2 — `aggregate_daily_to_monthly_sum` silent length mismatch
- `chart-solar-4wlz` P2 — `extraction.critical_fields._resolve` schema-drift silence
- `chart-solar-bx94` P3 — `era5_land.py` uses stdlib logging

## Security

### Filed
- **Magic-link login is GET + token in query string + SameSite=lax** —
  `backend/api/auth/magic_link.py:63` — vulnerable to login CSRF / cross-account
  attachment, plus token leak via Referer / browser history / log lines.
  Convert callback to POST consumed from a fragment-bearing frontend route.
- **Stripe webhooks trust unvalidated `metadata.user_id`; no FK on
  `user_entitlements.user_id`** — `backend/services/stripe_webhook_router.py:123`
  + `backend/db/entitlement_models.py:49` — anything that can craft a checkout
  session with arbitrary metadata can grant a paid tier to any string. Validate
  against `users.id` and add a real FK.
- **No rate limiting on auth endpoints** — `backend/api/auth/magic_link.py:45`
  — Resend-billed spam vector + reputation damage. Add per-IP and per-email
  token-bucket against the existing Redis dependency.
- **No request body size cap** — `backend/api/forecast.py:57` +
  `backend/api/stripe_webhook.py:46` — memory-DoS via large bodies that are
  buffered before validation/signature check. Enforce in middleware or at the
  reverse proxy.
- **PII (email) emitted in structured logs** — `backend/services/auth_service.py:96,146`
  — widens blast radius for any log-aggregator breach. Log `user_id` only,
  drop `email` from `auth.magic_link_issued` and `auth.session_created`.
- **`current_tier()` hardcoded to `Tier.FREE`** —
  `backend/entitlements/guards.py:23` — `require_feature` would universally
  402 once any paid feature is gated. Wire to `tier_for_user` before using
  the guard.

### Acknowledged, not filed
- `response.delete_cookie` lacks attribute match — mostly cosmetic
  (server-side session is revoked correctly); fold into the magic-link issue
  if it gets touched.
- `/api/health` exposes per-component status — operational decision, not a
  vulnerability today.
- `Cookie(... alias=settings.…)` evaluated at import time — operator footgun,
  not exploitable.

## Code quality

### Filed
- **`canonical_request_hash` collapses int/float** — `backend/infra/idempotency.py:48`
  — JSON parse normalizes `1.0` → `1`, so two semantically different forecast
  bodies hash identically. Real correctness bug.
- **`claim_idempotency_slot` race fallback returns cached body without running
  the side effect** — `backend/infra/idempotency.py:182` — client receives a
  `job_id` for a job that was never enqueued.
- **`@idempotent` decorator SELECT-then-INSERT race duplicates side effects** —
  `backend/infra/idempotency.py:215` — concurrent identical-key requests both
  miss the SELECT, both run the handler, only one INSERT wins. Reuse the
  `claim_idempotency_slot` pattern.
- **`get_job` swallows every exception** — `backend/workers/queue.py:66` —
  Redis outage gets reported as 404, not 5xx; operator has nothing to debug.
  Catch `NoSuchJobError` only.
- **`aggregate_daily_to_monthly_sum` silently swallows length mismatches** —
  `backend/providers/irradiance/_aggregation.py:31` — silently disables snow
  loss derate site-wide on a malformed Open-Meteo payload.
- **`extraction.critical_fields._resolve` fails silently on schema drift** —
  `backend/extraction/critical_fields.py:33` — audit silently green-lights
  low-confidence runs if `CRITICAL_FIELDS` paths drift from `ExtractedProposal`.
  Validate the path table at module import time.
- **`era5_land.py` uses stdlib `logging` instead of structlog** —
  `backend/providers/irradiance/era5_land.py:50` — drops structured fields,
  correlation id, Sentry tag. One-line fix.

### Acknowledged, not filed
- `cast(CursorResult[Any], ...)` repeated in `audit_service.py` — ~4 sites,
  one-line each; bundle as a minor cleanup if anything else in the file changes.
- NaN check via self-equality in `opportunity_cost.py` — readable enough.
- Stale `auth_models.py` docstring referring to a now-merged FK — fix opportunistically.
- `/api/irradiance` returns 200 `{"status": "not_implemented"}` — should be 501
  or removed; bundle with whatever wires the route up.
- `BaseHTTPMiddleware` use in `SessionMiddleware` and `CorrelationIdMiddleware`
  — performance smell, see perf section.
- `forecast_service.submit_forecast` trampoline — symmetric with `get_forecast_job`,
  leave alone until SQS adapter lands.

## Architecture

### Filed
- **Add lint-imports contracts: `backend.db -/-> backend.providers` and
  `backend.infra -/-> backend.db / backend.database`** — both are violated by
  `db/tmy_cache.py` and `infra/idempotency.py` respectively. The
  `engine`/`domain` purity contract is well-enforced; these two siblings would
  catch existing real regressions.
- **Engine pipeline: collapse parallel registries into one** —
  `backend/engine/pipeline.py:66`, `backend/engine/registry.py` — adding a step
  requires three coordinated edits across `ENGINE_STEP_ORDER`, `_STEPS` and
  `_ADAPTERS`. Either fold arg-extraction into each step, or attach the adapter
  to `@register`. Bundle: drop `Era5LandSibling` Protocol (one impl + one stub),
  hoist `_scaled_dc` from a sibling step's underscore-private into a shared
  helper, and move `run_monthly_rollover` out of `engine/integration/nbt.py`
  into a regulator-neutral location.
- **`engine/inputs.py` regime configs `apply()` lazy-import step modules** —
  `backend/engine/inputs.py:49` — leaky strategy pattern, schema and
  dispatcher in one module. Move dispatch into `steps/export_credit.py` and
  drop the `apply()` methods.
- **`db/tmy_cache.py` mixes ORM model + cache helpers + attribution
  registry** — `backend/db/tmy_cache.py` — split: ORM into
  `db/tmy_cache_models.py`, helpers into a service or provider adapter,
  attribution registry into `providers/irradiance/`.

### Acknowledged, not filed
- `backend.database` shared `SessionLocal` pattern with module-level dereference
  — bigger refactor; the existing `get_session` async generator is already
  usable. Adopt incrementally rather than a flag-day rewrite.
- Geographic bounding-box auto-routing in `providers/irradiance/__init__.py` —
  borderline ZFC; this is coverage-area routing, not classification. Move boxes
  to config opportunistically.
- Module-level mutable state in `eventbus.py`, `retry.py` — has documented
  test-only escape hatches; leave for now.

### Well-designed (called out)
- `backend.domain` separation from `backend.providers` keeps engine pure.
- Snapshot pinning in `engine/snapshot.py` (canonical-JSON + `engine_version`).
- Discriminated-union `ExportCreditConfig` fails bad regime/field combos at
  parse time.
- `infra/http.py` + `infra/retry.py` integration with the `test_no_raw_httpx_outside_infra`
  enforcement test.
- Vertex client refusing to start without ZDR flags (production won't start, not
  a runtime warning).

## Tests

### Filed
- **Test coverage cluster** — single issue covering the gaps that matter:
  - `backend/extraction/critical_fields.py` — no tests
  - `backend/providers/email/resend.py` — no direct tests
  - `backend/api/auth/session_middleware.py` — exception branch + anonymous-fallthrough uncovered
  - `backend/workers/forecast_worker.py` — no error-path test; `dispatch(ForecastCompleted)` not asserted
  - `backend/infra/http.py` — no direct unit tests; bug breaks every provider silently
  - `backend/infra/idempotency.py` — TTL-expiry branch + concurrent-claim race not covered
- **Test-suite scaffolding cleanup** — duplicate Postgres-skip logic across 4
  files (drift), per-file `register_subscribers()` foot-gun, ad-hoc
  `synthetic_tmy` in 4 test files, hypothesis `nightly` profile registered but
  never run. Hoist into `conftest.py`.

### Acknowledged, not filed
- Brittleness in `test_retry.py` log-string assertion + `time.sleep(0.06)` —
  fold into the scaffolding cleanup if touched.
- `MagicMock` over `_get_job` in `test_services_forecast.py` — locks in
  implementation; refactor when `forecast_service` next changes.
- Asyncio.run() inside an async test in `test_stripe_webhook.py:368` — fix
  opportunistically.
- 5-second forecast budget claimed in `docs/ENGINEERING.md` has no `slow`-marked
  test — reasonable to add when CI runner perf stabilizes; not load-bearing today.

## Performance & async correctness

### Filed
- **`httpx.AsyncClient` instantiated per call** — `backend/infra/http.py:54,74`
  — fresh TCP+TLS handshake each retry, multiplied by `max_attempts=4` and
  per-job TMY fetches. Hold one client per `service` key for the process
  lifetime.
- **`asyncio.run` per forecast job** — `backend/workers/forecast_worker.py:73`
  — fresh event loop per job means no asyncpg pool / httpx pool reuse across
  jobs. Persistent loop per worker process.
- **DB session held across email send** — `backend/api/auth/magic_link.py:54`
  + `backend/services/auth_service.py:84` — Resend latency parks a connection
  slot; pool starves at ~15 concurrent logins. Send email outside the
  `async with` block.
- **Sync redis enqueue from async route** — `backend/workers/queue.py:43` via
  `backend/api/forecast.py:81` — every `POST /forecast` blocks the event loop
  for the duration of `LPUSH`. Wrap in `asyncio.to_thread` or use
  `redis.asyncio`.
- **TOU period scan not memoized in `_bill_tou`** —
  `backend/engine/steps/tariff.py:146` — `battery_dispatch` already memoizes
  the 576-cell `(month, weekday, hour)` map; `_bill_tou` and
  `apply_nem_one_for_one` re-scan every hour every Monte Carlo path. Same
  primitive, hoist the memo.
- **`BaseHTTPMiddleware` → pure ASGI** — `backend/api/auth/session_middleware.py:36`
  + `backend/infra/middleware.py:19` — well-known Starlette slow-path; both
  middlewares are short enough that conversion is a few lines.
- **Forecast payload re-validated through Pydantic twice** — pure waste on the
  hot path; bundle with the worker `asyncio.run` fix.

### Acknowledged, not filed
- aioboto3 builds a client per call — only matters under TTL-sweep; revisit
  when the sweep job exists.
- No explicit pool sizing on async engine — defaults are conservative; add
  config knobs the next time pool tuning lands.
- Monte Carlo path loop in pure Python — only matters once paths × hold_years
  gets larger; profile first.
- `tier_for_user` per-request DB hit when `current_tier` is wired up — memoize
  on `request.state` from the session middleware at that time.

## Notes

- Codebase is unusually disciplined about exception handling, structured
  logging, Pydantic at IO boundaries, engine purity, and test architecture
  (the `test_no_raw_httpx_outside_infra` source-scan is a gem). The findings
  above are all real but the baseline is healthy — most of what filed is
  genuine bug or load-bearing perf, not style/process.
- ZFC is well-respected: extraction is properly delegated to Vertex with a
  Pydantic schema at the boundary; no regex on equipment names; no per-installer
  template fingerprinting; no keyword document classifiers.
