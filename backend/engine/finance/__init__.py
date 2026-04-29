"""Pure-math finance helpers used by the engine pipeline.

The pipeline's `finance` step composes the modules here:

* `amortization` — fixed + variable-rate loan schedules
* (future) NPV / IRR / MIRR / discounted payback / LCOE per chart-solar-oqt

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

__all__ = [
    "AmortizationRow",
    "AmortizationSchedule",
    "amortize",
    "amortize_variable",
    "dealer_fee_effective_apr",
    "monthly_payment",
]
