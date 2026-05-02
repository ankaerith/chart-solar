# Test fixtures

## `legacy_solar_tracker_2025.json`

A 25-year financial projection produced by the predecessor system at
[ankaerith/solar-tracker](https://github.com/ankaerith/solar-tracker)
(the single-user repo this product evolved from). One real install:
20.68 kW DC, $42,882 system cost, two-loan finance stack, PSE territory.

**Provenance:** `data/solar_financial_data.json` from the legacy repo
at commit `main` as of the import date encoded in the file's
`extracted_at` field. Re-pull from the legacy repo if a refresh is
needed; the file is verbatim (no transformation on import).

**What it pins:** the per-year `net_cash_flow` ledger plus an
`npv_summary` block (NPV at 6%/8% over 15/20/25-yr horizons). Our engine
math (`backend.engine.finance.npv`) reproduces those NPVs to ~13
decimals when fed the same year-1..year-25 cashflow stream — the legacy
ledger is therefore an independent cross-check of our NPV primitive.

**What it does *not* pin:** full-pipeline reproduction. The legacy
system used PVWatts for production (we use pvlib's `ModelChain`,
typically 3-8% off), modelled two parallel loans (we model one), and
included an `interest_tax_savings` term driven by a `marginal_tax_rate`
input the engine does not yet ingest. End-to-end "feed inputs, run the
engine, match within 1%" is tracked separately in `chart-solar-azou`.

The fixture itself is intentionally not regenerated against pvlib — its
value as a golden is precisely that an unrelated production model
landed at numerically identical NPVs from the same cashflow stream, and
that's the regression we're asserting against.
