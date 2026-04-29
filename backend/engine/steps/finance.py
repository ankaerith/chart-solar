"""Financial roll-up: loans, incentives, NPV / IRR / payback.

The pure-math primitives — fixed/variable amortization, NPV, IRR,
MIRR, discounted payback, LCOE, crossover year — already live in
``backend.engine.finance`` and are covered by the
``test_finance_*`` suites. What remains is the *pipeline orchestrator*:
a registered ``engine.finance`` step that composes those primitives
against ``ForecastState`` (per-year energy from the degradation curve,
per-year bill from the tariff step + export credit, loan schedule from
SystemInputs, jurisdiction-scoped incentives) and emits a per-year
cashflow stream + headline metrics.

Until that orchestrator lands, this module stays a stub — the
pipeline (chart-solar-cm4i) skips ``engine.finance`` when it isn't
registered. See ``backend.engine.finance`` for the building blocks.
"""
