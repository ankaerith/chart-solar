"""Sale-scenario modeling (chart-solar-7fb).

Covers the LBNL home-value uplift, transaction-cost drag, optional
loan-payoff handling, the probability-weighted aggregate, and the
schema invariants (probabilities sum to 1, non-empty, and the model
gracefully handles a sale year past the modelled horizon).
"""

from __future__ import annotations

import pytest

from backend.domain.hold import (
    DEFAULT_HOME_VALUE_UPLIFT_PER_W_DC,
    DEFAULT_TRANSACTION_COSTS_PCT,
    HoldYearProbability,
    SaleScenarioInputs,
)
from backend.engine.finance.sale import (
    expected_sale_npv,
    home_value_uplift,
)


def _flat_inputs(years: list[int], probs: list[float]) -> SaleScenarioInputs:
    return SaleScenarioInputs(
        hold_year_probabilities=[
            HoldYearProbability(year=y, probability=p) for y, p in zip(years, probs, strict=True)
        ]
    )


def test_default_uplift_matches_lbnl_hoen() -> None:
    inputs = _flat_inputs([10], [1.0])
    uplift = home_value_uplift(dc_kw=8.0, sale_year=10, inputs=inputs)
    assert uplift == pytest.approx(8.0 * 1000.0 * DEFAULT_HOME_VALUE_UPLIFT_PER_W_DC)


def test_uplift_decay_fades_premium_linearly() -> None:
    """A 5 %/yr decay reduces the year-11 premium by 50 % vs year-1."""
    inputs = SaleScenarioInputs(
        home_value_decay_per_year=0.05,
        hold_year_probabilities=[HoldYearProbability(year=1, probability=1.0)],
    )
    base = home_value_uplift(dc_kw=10.0, sale_year=1, inputs=inputs)
    later = home_value_uplift(dc_kw=10.0, sale_year=11, inputs=inputs)
    assert base == pytest.approx(10.0 * 1000.0 * DEFAULT_HOME_VALUE_UPLIFT_PER_W_DC)
    assert later == pytest.approx(base * 0.5)


def test_uplift_decay_floors_at_zero() -> None:
    """An aggressive decay can't push the premium below zero."""
    inputs = SaleScenarioInputs(
        home_value_decay_per_year=0.10,
        hold_year_probabilities=[HoldYearProbability(year=1, probability=1.0)],
    )
    distant = home_value_uplift(dc_kw=8.0, sale_year=25, inputs=inputs)
    assert distant == 0.0


def test_expected_sale_npv_matches_undecorated_npv_when_uplift_is_zero() -> None:
    """With zero uplift + zero transaction costs + zero loan, the
    sale-scenario expected NPV collapses to plain `npv()` of the
    cashflows truncated to the (single) hold year."""
    from backend.engine.finance.cashflow import npv

    cashflows = [-20_000.0] + [2_000.0] * 10
    inputs = SaleScenarioInputs(
        home_value_uplift_per_w_dc=0.0,
        transaction_costs_pct=0.0,
        hold_year_probabilities=[HoldYearProbability(year=10, probability=1.0)],
    )
    result = expected_sale_npv(
        cashflows=cashflows,
        discount_rate=0.05,
        dc_kw=8.0,
        inputs=inputs,
    )
    assert result.expected_npv == pytest.approx(npv(0.05, cashflows))


def test_expected_sale_npv_adds_year_indexed_uplift_to_sale_year_cashflow() -> None:
    """Year-Y cashflow gets `uplift - closing - loan_payoff` added.
    Verify the math by reconstructing the truncated stream by hand."""
    from backend.engine.finance.cashflow import npv

    cashflows = [-20_000.0] + [2_000.0] * 10
    inputs = SaleScenarioInputs(
        home_value_uplift_per_w_dc=4.0,
        transaction_costs_pct=0.06,
        hold_year_probabilities=[HoldYearProbability(year=8, probability=1.0)],
    )
    result = expected_sale_npv(
        cashflows=cashflows,
        discount_rate=0.05,
        dc_kw=8.0,
        inputs=inputs,
    )
    uplift = 8.0 * 1000.0 * 4.0
    closing = uplift * 0.06
    expected_truncated = list(cashflows[:9])
    expected_truncated[-1] = expected_truncated[-1] + uplift - closing
    assert result.expected_npv == pytest.approx(npv(0.05, expected_truncated))


def test_expected_sale_npv_subtracts_loan_payoff_from_sale_year() -> None:
    """A non-zero remaining loan reduces year-Y net cashflow."""

    cashflows = [-5_000.0] + [3_000.0] * 10
    inputs = SaleScenarioInputs(
        home_value_uplift_per_w_dc=4.0,
        transaction_costs_pct=0.06,
        hold_year_probabilities=[HoldYearProbability(year=5, probability=1.0)],
    )
    no_loan = expected_sale_npv(
        cashflows=cashflows,
        discount_rate=0.05,
        dc_kw=8.0,
        inputs=inputs,
    )
    with_loan = expected_sale_npv(
        cashflows=cashflows,
        discount_rate=0.05,
        dc_kw=8.0,
        inputs=inputs,
        loan_payoff_at_year=lambda y: 3_000.0,
    )
    # The loan payoff reduces year-5 cashflow by 3000; NPV change is
    # the discounted version of that.
    assert no_loan.expected_npv > with_loan.expected_npv
    assert with_loan.expected_npv == pytest.approx(no_loan.expected_npv - 3_000.0 / (1.05**5))


def test_expected_sale_npv_probability_weights_outcomes() -> None:
    """A 50/50 split between two sale years averages the per-year NPVs."""
    cashflows = [-10_000.0] + [1_500.0] * 15
    inputs = SaleScenarioInputs(
        hold_year_probabilities=[
            HoldYearProbability(year=5, probability=0.5),
            HoldYearProbability(year=15, probability=0.5),
        ]
    )
    result = expected_sale_npv(
        cashflows=cashflows,
        discount_rate=0.05,
        dc_kw=6.0,
        inputs=inputs,
    )
    assert len(result.outcomes) == 2
    npv_avg = (result.outcomes[0].npv_at_sale + result.outcomes[1].npv_at_sale) / 2.0
    assert result.expected_npv == pytest.approx(npv_avg)


def test_sale_year_past_horizon_caps_at_final_year() -> None:
    """The sale-year distribution may extend past the user's hold —
    the wrapper caps the per-outcome sale year at len(cashflows)-1
    rather than crashing."""
    cashflows = [-5_000.0] + [1_000.0] * 5  # only 5 years modelled
    inputs = SaleScenarioInputs(
        hold_year_probabilities=[HoldYearProbability(year=20, probability=1.0)],
    )
    result = expected_sale_npv(
        cashflows=cashflows,
        discount_rate=0.05,
        dc_kw=4.0,
        inputs=inputs,
    )
    assert result.outcomes[0].sale_year == 5  # capped to len-1


def test_sale_inputs_rejects_probabilities_that_do_not_sum_to_one() -> None:
    with pytest.raises(ValueError, match="must sum to 1.0"):
        SaleScenarioInputs(
            hold_year_probabilities=[
                HoldYearProbability(year=5, probability=0.4),
                HoldYearProbability(year=10, probability=0.4),
            ]
        )


def test_sale_inputs_rejects_empty_distribution() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        SaleScenarioInputs(hold_year_probabilities=[])


def test_default_transaction_costs_is_six_percent() -> None:
    """Documenting the constant so a downstream consumer doesn't
    silently rebase off a stale rule of thumb."""
    assert DEFAULT_TRANSACTION_COSTS_PCT == pytest.approx(0.06)
