"""Sale-scenario modeling.

Most homeowners don't hold a system for its full design life — they
sell. The math here answers "if I sell at year Y, what is my net
wealth?" and aggregates that across a probability distribution over
candidate sale years.

Three terms drive year-Y wealth on top of the engine's deterministic
cashflows:

* **Home-value uplift.** LBNL Hoen et al. 2015 found a ~$4/W (DC)
  premium on US home sale prices for owned PV systems. Applied as a
  one-shot addition to the sale-year cashflow; an optional linear
  decay term lets callers fade the premium toward zero over the
  system's lifetime if they suspect the Hoen number doesn't hold for
  older systems.
* **Transaction costs.** Closing costs cut into the premium; 6 % is
  the US realtor + title-fee rule of thumb.
* **Remaining loan balance.** Paid off at sale (assumability is
  jurisdiction-specific — most US loans are not assumable, so the
  default is to assume payoff). Callers passing a custom
  ``loan_payoff_at_year`` can model assumability by returning ``0``.

The wrapper is pure: deterministic, no IO, mirrors
:mod:`backend.engine.finance.cashflow` style. Pipeline integration is
deliberately out of scope here — the wizard wires into
``expected_sale_npv`` once the UI lands. See chart-solar-7fb.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from backend.domain.hold import SaleScenarioInputs
from backend.engine.finance.cashflow import npv


class SaleScenarioOutcome(BaseModel):
    """Per-sale-year evaluation."""

    sale_year: int
    probability: float
    home_value_uplift: float
    transaction_costs: float
    loan_payoff: float
    npv_at_sale: float


class SaleScenarioResult(BaseModel):
    """Probability-weighted aggregate across the hold distribution."""

    inputs: SaleScenarioInputs
    expected_npv: float
    outcomes: list[SaleScenarioOutcome]


def home_value_uplift(
    *,
    dc_kw: float,
    sale_year: int,
    inputs: SaleScenarioInputs,
) -> float:
    """Estimated PV premium added to the home sale price.

    Linear-decay model: at year 1 the full per-watt uplift applies;
    at year ``1 / decay`` the uplift is zero. ``decay = 0`` (default)
    means the premium is constant — the LBNL headline.
    """
    base = dc_kw * 1000.0 * inputs.home_value_uplift_per_w_dc
    fade = max(0.0, 1.0 - inputs.home_value_decay_per_year * (sale_year - 1))
    return base * fade


def expected_sale_npv(
    *,
    cashflows: list[float],
    discount_rate: float,
    dc_kw: float,
    inputs: SaleScenarioInputs,
    loan_payoff_at_year: Callable[[int], float] | None = None,
) -> SaleScenarioResult:
    """Probability-weighted NPV across the sale-year distribution.

    ``cashflows`` is the year-indexed cashflow stream from the
    deterministic finance step; index 0 is the homeowner's initial
    outlay (always negative on a cash buy). For each candidate sale
    year ``y``, this function:

    1. Truncates cashflows to the first ``y + 1`` entries (year 0
       outlay through year ``y`` operating cashflow).
    2. Adds the home-value uplift, less transaction costs and any
       remaining loan, to year ``y``'s cashflow.
    3. Computes NPV of the truncated stream at ``discount_rate``.

    The expected NPV is the probability-weighted sum across all
    candidate sale years. Outcomes are returned alongside so a chart
    can render the per-year distribution behind the headline.
    """
    if not cashflows:
        raise ValueError("cashflows must be non-empty")
    if dc_kw <= 0.0:
        raise ValueError("dc_kw must be > 0")
    payoff_fn: Callable[[int], float] = (
        loan_payoff_at_year if loan_payoff_at_year is not None else (lambda _: 0.0)
    )

    outcomes: list[SaleScenarioOutcome] = []
    expected_npv = 0.0
    for entry in inputs.hold_year_probabilities:
        sale_year = entry.year
        if sale_year >= len(cashflows):
            # Probability mass beyond the modelled horizon: cap to the
            # final-year cashflow stream and keep the uplift / payoff
            # math at year=horizon. Drops a warning later in the chart.
            sale_year = len(cashflows) - 1
        uplift = home_value_uplift(dc_kw=dc_kw, sale_year=sale_year, inputs=inputs)
        closing = uplift * inputs.transaction_costs_pct
        payoff = payoff_fn(sale_year)
        truncated = list(cashflows[: sale_year + 1])
        truncated[sale_year] = truncated[sale_year] + uplift - closing - payoff

        path_npv = npv(discount_rate, truncated)
        outcomes.append(
            SaleScenarioOutcome(
                sale_year=sale_year,
                probability=entry.probability,
                home_value_uplift=uplift,
                transaction_costs=closing,
                loan_payoff=payoff,
                npv_at_sale=path_npv,
            )
        )
        expected_npv += entry.probability * path_npv

    return SaleScenarioResult(inputs=inputs, expected_npv=expected_npv, outcomes=outcomes)


__all__ = [
    "SaleScenarioOutcome",
    "SaleScenarioResult",
    "expected_sale_npv",
    "home_value_uplift",
]
