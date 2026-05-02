"""Pure-math finance helpers used by the engine pipeline.

The pipeline's `finance` step composes the modules here:

* `amortization` — fixed + variable-rate loan schedules
* `cashflow` — NPV / IRR / MIRR / discounted payback / LCOE / crossover
* `opportunity_cost` — HYSA / mortgage / S&P overlays for the
  capital-allocation chart
* `sale` — probability-weighted sale-scenario NPV with LBNL Hoen
  home-value uplift

Everything is deterministic and side-effect-free — no IO, no providers,
no engine state. Tests live in `backend/tests/test_finance_*`.
"""

from backend.engine.finance.amortization import (
    AmortizationRow,
    AmortizationSchedule,
    amortize,
    amortize_variable,
    dealer_fee_effective_apr,
    monthly_payment,
)
from backend.engine.finance.cashflow import (
    annualized_return,
    crossover_year,
    discounted_payback_years,
    irr,
    lcoe,
    mirr,
    npv,
)
from backend.engine.finance.opportunity_cost import (
    HYSA_BASELINE,
    MORTGAGE_PAYDOWN_BASELINE,
    SP500_BASELINE,
    CapitalAllocationBaseline,
    alternative_wealth_path,
    compare_npv_at_alternatives,
    cumulative_solar_wealth,
)
from backend.engine.finance.sale import (
    SaleScenarioOutcome,
    SaleScenarioResult,
    expected_sale_npv,
    home_value_uplift,
)

__all__ = [
    "AmortizationRow",
    "AmortizationSchedule",
    "CapitalAllocationBaseline",
    "HYSA_BASELINE",
    "MORTGAGE_PAYDOWN_BASELINE",
    "SP500_BASELINE",
    "SaleScenarioOutcome",
    "SaleScenarioResult",
    "alternative_wealth_path",
    "amortize",
    "amortize_variable",
    "annualized_return",
    "compare_npv_at_alternatives",
    "crossover_year",
    "cumulative_solar_wealth",
    "dealer_fee_effective_apr",
    "discounted_payback_years",
    "expected_sale_npv",
    "home_value_uplift",
    "irr",
    "lcoe",
    "mirr",
    "monthly_payment",
    "npv",
]
