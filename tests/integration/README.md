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

Each region pairs the engine with the **definitive regional authority** as oracle — different lab, same data product family — so drift reflects engine variance, not cross-product noise.

| Region | Oracle (definitive source) | Engine path | Tolerance | Why |
|---|---|---|---|---|
| CONUS | NREL PVWatts API (`dataset=tmy3`) | pvlib + NSRDB | ±5 % | pvlib *is* the PVWatts algorithm; NSRDB is the same data family as PVWatts.tmy3 stations. Bit-near agreement expected. |
| UK / EU | JRC PVGIS PVcalc (`re.jrc.ec.europa.eu/api/v5_2/PVcalc`) | pvlib + PVGIS | ±10 % (provisional) | Same data product (PVGIS-SARAH-2 on both sides) but different physics impl (pvlib's PVWatts vs JRC's PVcalc). Tightens to ±5 % once chart-solar-gi58 routes the engine through PVcalc directly. |
| Rest of world | PVWatts API (`dataset=intl`) — fallback only | pvlib + Open-Meteo | wider; case-by-case | No clear regional authority; ASHRAE-vs-Open-Meteo drift is real and unavoidable. |

Other metric classes:

| Metric class | Tolerance | Why |
|---|---|---|
| Monthly AC production | ±8 % | Element-wise; monthly-shape drift is larger than annual roll-up. |
| NPV / IRR | ±1 % | Closed-form math; closer agreement is expected. |
| Monthly bills | ±2 % | Hand-derived; tariff math is deterministic. |

Use `oracles/pvwatts.py build-case` for CONUS and rest-of-world cases (auto-routes `tmy3`/`intl` by lat/lon). Use `oracles/pvgis.py build-case` for UK/EU cases — JRC PVcalc is the European authority, not PVWatts.intl.

## Oracle inventory

- **NREL PVWatts v8 API** — US regional authority for production. `oracles/pvwatts.py`. Auto-routes `tmy3` for CONUS, `intl` for rest of world.
- **JRC PVGIS PVcalc (v5.2)** — European regional authority for production. `oracles/pvgis.py`. Public API; no key required. Pairs JRC's reference physics with PVGIS-SARAH-2 / NSRDB / ERA5 data — the definitive EU/UK standard.
- **PySAM** — full-stack production + battery + tariff + finance. Deferred; tracks chart-solar-b5x4.
- **Hand-derived** — finance / tariff edge cases (flat tariff + zero load → known closed form for export revenue).

## Adding a case

1. Drop a new `cases/<name>.json` with `inputs` filled in (no oracle, empty expected).
2. Build the oracle block — pick by region:
   - **CONUS / rest of world**: `uv run python -m tests.integration.oracles.pvwatts build-case cases/<name>.json`
   - **UK / EU**: `uv run python -m tests.integration.oracles.pvgis build-case cases/<name>.json`
3. Hand-derive finance / tariff numbers if applicable and pin them with appropriate tolerance.
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
│   ├── pvwatts.py                       # NREL PVWatts (US regional authority)
│   └── pvgis.py                         # JRC PVGIS PVcalc (EU regional authority)
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
- chart-solar-gi58 — EPIC: regional-authority physics (route engine to PVcalc for UK/EU; supersedes ADR 0006)
- chart-solar-hhq8 — ADR + PVcalc adapter (child of gi58)
- chart-solar-0wul — Engine routing + pvlib fallback (child of gi58)
- chart-solar-3y74 — Spike: full-API engine evaluation
- chart-solar-cyho — broader audit of hardcoded provider URLs
- chart-solar-b5x4 — PySAM battery dispatch spike
- chart-solar-n1hg — PySAM URDB/tariff spike
