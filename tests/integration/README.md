# Integration tests

Black-box HTTP harness validating the forecast pipeline end-to-end against external oracles. Distinct from `backend/tests/` (pytest, in-process, per-step math).

## What this validates

For each curated case the harness:
1. POSTs `inputs` (a `ForecastInputs` body) to `POST /api/forecast`.
2. Polls `GET /api/forecast/{job_id}` until the worker reports a terminal status.
3. Walks the case's `expected` table, comparing each metric against the result within its declared tolerance.

Production numbers are validated against **NREL's PVWatts v8 API** (`developer.nlr.gov`) — a cross-implementation check on `engine.dc_production` (NREL Fortran vs. our pvlib Python wrapper). Finance / tariff metrics are hand-derived per case; PySAM as a second oracle is deferred.

## Running

```bash
# 1. Boot the API stack (Postgres + Redis + RQ worker + FastAPI).
#    See the project root README for the canonical command.
docker compose up

# 2. From the repo root:
uv run python -m tests.integration.harness.run                  # all cases
uv run python -m tests.integration.harness.run --case phoenix   # one case
uv run python -m tests.integration.harness.run --validate-only  # load + schema-check only, no API call
```

`--api-base-url` overrides the default `http://localhost:8000` (or set `API_BASE_URL` in `.env` at the repo root). Exits non-zero if any case fails — CI-gating-ready once we wire it.

## Case file shape

```jsonc
{
  "name": "phoenix_8kw_flat",
  "description": "Single-array 8 kW DC south at 30° tilt, APS flat tariff.",
  "inputs": { /* ForecastInputs body — passed verbatim to /api/forecast */ },
  "oracle": {
    "production": {
      "source": "pvwatts_v8",
      "endpoint": "https://developer.nlr.gov/api/pvwatts/v8.json",
      "fetched_at": "2026-05-02T12:00:00Z",
      "requests": [ /* one entry per sub-array */ ],
      "responses": [ /* matching responses */ ]
    }
  },
  "expected": {
    "artifacts/engine.dc_production/annual_ac_kwh":  { "kind": "scalar", "value": 14210, "tol_pct": 5 },
    "artifacts/engine.finance/npv_25yr_6pct":        { "kind": "scalar", "value": 32100, "tol_pct": 1 }
  }
}
```

`expected` keys are slash-separated paths into the API response's `result` tree. The separator is `/` (not `.`) because engine artifact keys themselves contain dots (`engine.dc_production`, `engine.snow`). Loose keying (rather than a typed accessor) keeps the harness independent of the backend's evolving artifact schema.

Multi-pass cases (e.g., `seattle_dual_array_2pass`) use `inputs_arrays: list[dict]` instead of `inputs`. Each entry is a complete forecast body; the harness submits each, sums production results across runs, then compares the sum against `expected`. Workaround for multi-array systems until `chart-solar-h3y6` (multi-array `SystemInputs`) lands.

## Tolerance policy

| Metric class | Tolerance | Why |
|---|---|---|
| Annual AC production (CONUS) | ±5 % vs PVWatts.tmy3 | Both sides use NSRDB-family TMY data, same algorithm. ~3 % drift expected. |
| Annual AC production (non-CONUS) | ±10 % vs PVWatts.intl | PVWatts.intl uses ASHRAE TMY; engine uses PVGIS (JRC SARAH/ERA5) for UK/EU. Two unrelated reanalysis products — mid-single-digit drift in cloudy/temperate climates is the realistic best case. |
| Monthly AC production | ±8 % | Element-wise; monthly-shape drift is larger than annual roll-up. |
| NPV / IRR | ±1 % | Closed-form math; closer agreement is expected. |
| Monthly bills | ±2 % | Hand-derived; tariff math is deterministic. |

The PVWatts oracle's `build-case` CLI auto-routes (`tmy3` for CONUS, `intl` elsewhere) and applies the matching tolerance. Override per-case in the JSON if a specific site needs tighter or looser bounds.

## Oracle inventory

- **PVWatts v8 API** — production-only. NREL's reference implementation. `oracles/pvwatts.py` (issue chart-solar-90dz).
- **PySAM** — full-stack production + battery + tariff + finance. Deferred; tracks chart-solar-b5x4.
- **Hand-derived** — finance / tariff edge cases (flat tariff + zero load → known closed form for export revenue).

## Adding a case

1. Drop a new `cases/<name>.json` with `inputs` filled in (no oracle, empty expected).
2. Build the oracle block: `uv run python -m tests.integration.oracles.pvwatts build-case cases/<name>.json` (issue chart-solar-90dz).
3. Fill in `expected` — copy oracle production numbers under the matching `engine.dc_production.*` paths; hand-derive finance numbers and pin them with appropriate tolerance.
4. Run: `uv run python -m tests.integration.harness.run --case <name>`.

## Layout

```
tests/integration/
├── README.md                            # this file
├── cases/                               # one JSON per curated case (committed)
│   ├── _sample.json                     # leading-underscore = skipped by default-load
│   ├── boston_8kw_clear.json            # CONUS, single-array
│   ├── edinburgh_4kw_clear.json         # UK, single-array (PVGIS engine, intl oracle)
│   ├── london_4kw_clear.json            # UK, single-array (PVGIS engine, intl oracle)
│   ├── phoenix_8kw_clear.json           # CONUS, single-array
│   ├── san_diego_8kw_clear.json         # CONUS, single-array
│   └── seattle_dual_array_2pass.json    # CONUS, multi-pass (4.4 N + 16.28 S)
├── oracles/                             # reference-data fetchers + case-builders
│   └── pvwatts.py                       # (issue chart-solar-90dz)
└── harness/                             # the runner
    ├── case.py                          # Pydantic schema for case files
    ├── client.py                        # async HTTP client (POST + poll)
    ├── compare.py                       # tolerance-aware diff
    └── run.py                           # `python -m tests.integration.harness.run`
```

## Related issues

- chart-solar-gbjt — epic
- chart-solar-lpm0 — scaffold (merged in #98)
- chart-solar-90dz — PVWatts oracle + case-builder (merged in #98; UK extension here)
- chart-solar-4af0 — stack boot + auth approach
- chart-solar-6wib — initial case slate (Phoenix, San Diego, Boston, Seattle 2-pass; merged in #98)
- chart-solar-h3y6 — multi-array engine support (Seattle is the validation oracle)
- chart-solar-9xi4 — engine production miss (closed via PR #99; harness flipped from 0/4 to 4/4 passing)
- chart-solar-cyho — broader audit of hardcoded provider URLs
- chart-solar-b5x4 — PySAM battery dispatch spike
- chart-solar-n1hg — PySAM URDB/tariff spike
