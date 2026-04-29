# 0006. Engine steps wrap pvlib; don't reimplement physics

**Decision**: Engine pipeline steps defer to pvlib for any modeling pvlib supports. Application code wraps pvlib with our state contract and supplies modifiers (parameters); it does not reimplement cell-temperature, inverter clipping, snow loss, or soiling.

**Status**: accepted

**Date**: 2026-04-29

## Context

The Phase 1a engine work spawned dedicated pipeline steps for cell-temperature derating (`engine.cell_temperature`, chart-solar-p9l), DC:AC inverter clipping (`engine.clipping`, chart-solar-5qe), monthly soiling (`engine.soiling`, chart-solar-743), and snow loss (`engine.snow`, chart-solar-9ji). The intent was that `engine.dc_production` would do the base ModelChain run and these steps would layer per-hour overrides on top for what-if / sensitivity analysis.

Three problems with that model:

1. **pvlib's `ModelChain.with_pvwatts` already applies cell-temperature derating (SAPM `open_rack_glass_glass` by default) and inverter saturation (`inverter_parameters['pdc0']`).** A dedicated `engine.cell_temperature` or `engine.clipping` step running afterwards would either no-op or double-count, depending on whether the pipeline disabled the built-in derate first.
2. **For soiling and snow, pvlib ships `pvlib.soiling.hsu` / `pvlib.soiling.kimber` and `pvlib.snow.coverage_nrel` / `pvlib.snow.loss_townsend`** — site-specific models driven by rainfall / snowfall / RH inputs. Hand-rolled lat-band defaults (the shortcut taken because rainfall + snowfall don't yet route through `TmyData`) reimplemented physics pvlib already encodes more accurately.
3. **The "user override" framing was wrong.** No end user knows their gamma_pdc, mount type, or DC:AC ratio off the top of their head. These knobs are extension points for the extraction pipeline (when a quoted spec sheet surfaces real values) — not user-facing toggles. Standalone pipeline steps suggesting otherwise added complexity without adding capability.

## Decision

- **`engine.dc_production` is the single point of pvlib physics.** Wraps `ModelChain.with_pvwatts`. Exposes `inverter_ac_kw`, `gamma_pdc`, `temperature_model` as keyword arguments — populated by extraction when available, defaults otherwise.
- **No standalone `engine.cell_temperature` step. No standalone `engine.clipping` step.** pvlib ModelChain handles both inside `dc_production`.
- **`engine.soiling` and `engine.snow` wrap pvlib's models** (`pvlib.soiling.hsu` / `pvlib.snow.loss_townsend`) once the irradiance providers carry the required monthly inputs (precipitation / snowfall / relative humidity).
- **`engine.degradation` keeps its hand-rolled implementation.** pvlib does not model multi-year capacity degradation; this is genuinely net-additive.
- **Finance / tariff / export-credit steps stay in app code.** pvlib doesn't own these domains.

## Consequences

**Enables:**
- One source of truth for solar physics — pvlib upgrades land everywhere with a version bump, not a code rewrite.
- Smaller surface area to test. The "is the cell-temp model accurate?" question moves to "does pvlib's published validation cover our use case?" — a documentation problem, not an engineering problem.
- Cleaner pipeline composition: `dc_production → degradation → tariff → export_credit → finance`, with `soiling` and `snow` slotting in once data is available.

**Constrains:**
- We need monthly precipitation + snowfall + RH columns on `TmyData` before soiling and snow can return non-trivial results. Until then both steps are no-ops. Phase 1a launches without them; that's acceptable per `PRODUCT_PLAN.md` § Geographic Scope (early sites are temperate-coastal, snow + arid-soiling effects are second-order).
- pvlib API stability is now a load-bearing dependency. Mitigated by the snapshot-pinning work (chart-solar-zkx, already merged) — every saved forecast pins `pvlib_version`.

**Trigger for revisiting:**
- A pvlib model produces a result that's clearly wrong for our domain and the upstream maintainers won't fix it. Then we fork that single model into our codebase, but keep the wrap-pvlib pattern for everything else.
- A regulator-published curve (CPUC ACC, UK SEG) requires hourly-rate behavior pvlib doesn't expose. (NEM 3.0 NBT and SEG live in `engine.export_credit`, which is already domain-owned, not pvlib-owned.)

## Implementation

- **Closes / supersedes**:
  - chart-solar-5qe (DC:AC clipping) — pvlib ModelChain handles it
  - chart-solar-p9l (cell-temperature derating) — pvlib ModelChain handles it
  - chart-solar-c3sm (cell-temp non-linear thermal) — pvlib has more sophisticated models if we ever need them
  - chart-solar-7g6u (clipping load-curve η) — pvlib has more accurate inverter models if we ever need them
  - chart-solar-q5uc (snow southern-hemisphere flip) — moot once pvlib drives snow from real monthly data
  - chart-solar-yitq (shared monthly-projection helper) — moot once soiling and snow no longer share my hand-rolled factor lists
- **Rescoped**:
  - chart-solar-743 (soiling) — wrap `pvlib.soiling`, blocked on data-infra bead below
  - chart-solar-9ji (snow) — wrap `pvlib.snow`, blocked on data-infra bead below; folds in chart-solar-ujcb (Townsend upgrade)
- **New**:
  - "Extend irradiance providers with monthly precipitation + snowfall + RH columns" — unblocks pvlib soiling / snow

## References

- `PRODUCT_PLAN.md` § Architecture: Extensible Modeling Engine
- `PRODUCT_PLAN.md` § Cognition Architecture (the ZFC principle: physics in libraries, cognition in models, app code is glue)
- pvlib documentation: `pvlib.modelchain.ModelChain.with_pvwatts`, `pvlib.soiling`, `pvlib.snow`, `pvlib.temperature`
- Beads: chart-solar-uqp, chart-solar-743, chart-solar-9ji
