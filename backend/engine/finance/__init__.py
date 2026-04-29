"""Pure-math finance helpers used by the engine pipeline.

The pipeline's `finance` step composes the modules here:

* `amortization` — fixed + variable-rate loan schedules
* `cashflow` — NPV / IRR / MIRR / discounted payback / LCOE / crossover

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

__all__ = [
    "AmortizationRow",
    "AmortizationSchedule",
    "amortize",
    "amortize_variable",
    "annualized_return",
    "crossover_year",
    "dealer_fee_effective_apr",
    "discounted_payback_years",
    "irr",
    "lcoe",
    "mirr",
    "monthly_payment",
    "npv",
]
