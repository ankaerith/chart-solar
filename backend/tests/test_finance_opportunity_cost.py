"""Capital-allocation overlay primitives (chart-solar-d90).

Covers the alternative wealth path math (HYSA / mortgage / S&P
compounding), the npv-at-alternative-rate comparison, the cumulative
solar wealth helper, and the boundary-condition rejections.
"""

from __future__ import annotations

import math

import pytest

from backend.engine.finance.opportunity_cost import (
    HYSA_BASELINE,
    MORTGAGE_PAYDOWN_BASELINE,
    SP500_BASELINE,
    CapitalAllocationBaseline,
    alternative_wealth_path,
    compare_npv_at_alternatives,
    cumulative_solar_wealth,
)


def test_alternative_wealth_path_compounds_yearly() -> None:
    path = alternative_wealth_path(
        initial_outlay=20_000.0,
        annual_return=0.05,
        hold_years=3,
    )
    assert len(path) == 4
    assert path[0] == pytest.approx(20_000.0)
    assert path[1] == pytest.approx(20_000.0 * 1.05)
    assert path[2] == pytest.approx(20_000.0 * 1.05**2)
    assert path[3] == pytest.approx(20_000.0 * 1.05**3)


def test_alternative_wealth_path_zero_return_is_constant() -> None:
    path = alternative_wealth_path(
        initial_outlay=15_000.0,
        annual_return=0.0,
        hold_years=10,
    )
    assert path == [pytest.approx(15_000.0)] * 11


def test_alternative_wealth_path_hold_years_zero_returns_single_entry() -> None:
    path = alternative_wealth_path(
        initial_outlay=10_000.0,
        annual_return=0.07,
        hold_years=0,
    )
    assert path == [pytest.approx(10_000.0)]


def test_alternative_wealth_path_rejects_negative_hold_years() -> None:
    with pytest.raises(ValueError, match="hold_years"):
        alternative_wealth_path(initial_outlay=10_000.0, annual_return=0.05, hold_years=-1)


def test_alternative_wealth_path_rejects_nan_outlay() -> None:
    with pytest.raises(ValueError, match="finite"):
        alternative_wealth_path(initial_outlay=math.nan, annual_return=0.05, hold_years=10)


def test_compare_npv_at_alternatives_matches_npv_at_each_rate() -> None:
    """The comparison function is just `npv()` evaluated at each
    baseline's annual return — verify by recomputing by hand."""
    from backend.engine.finance.cashflow import npv

    cashflows = [-25_000.0] + [2_500.0] * 20
    baselines = [HYSA_BASELINE, MORTGAGE_PAYDOWN_BASELINE, SP500_BASELINE]
    table = compare_npv_at_alternatives(cashflows=cashflows, baselines=baselines)

    assert table[HYSA_BASELINE.label] == pytest.approx(npv(HYSA_BASELINE.annual_return, cashflows))
    assert table[MORTGAGE_PAYDOWN_BASELINE.label] == pytest.approx(
        npv(MORTGAGE_PAYDOWN_BASELINE.annual_return, cashflows)
    )
    assert table[SP500_BASELINE.label] == pytest.approx(
        npv(SP500_BASELINE.annual_return, cashflows)
    )


def test_compare_npv_at_alternatives_preserves_baseline_order() -> None:
    """Dict insertion order must mirror the input list order — the chart
    paints overlays in user-supplied order, not alphabetical."""
    cashflows = [-10_000.0] + [1_000.0] * 15
    custom = CapitalAllocationBaseline(label="ZZZ-Custom", annual_return=0.03)
    table = compare_npv_at_alternatives(
        cashflows=cashflows,
        baselines=[custom, HYSA_BASELINE],
    )
    assert list(table.keys()) == ["ZZZ-Custom", HYSA_BASELINE.label]


def test_compare_npv_at_alternatives_higher_discount_rate_lowers_npv() -> None:
    """A higher alternative return means solar has to clear a higher
    bar — its NPV at that rate should be lower."""
    cashflows = [-20_000.0] + [2_000.0] * 20
    low = compare_npv_at_alternatives(cashflows=cashflows, baselines=[HYSA_BASELINE])
    high = compare_npv_at_alternatives(cashflows=cashflows, baselines=[SP500_BASELINE])
    assert low[HYSA_BASELINE.label] > high[SP500_BASELINE.label]


def test_cumulative_solar_wealth_runs_running_sum() -> None:
    cashflows = [-10_000.0, 1_500.0, 2_000.0, 2_500.0]
    wealth = cumulative_solar_wealth(cashflows=cashflows)
    assert wealth == [
        pytest.approx(-10_000.0),
        pytest.approx(-8_500.0),
        pytest.approx(-6_500.0),
        pytest.approx(-4_000.0),
    ]


def test_default_baseline_rates_match_documented_values() -> None:
    """Pin the documented constants so the legend captions in the
    chart can't drift out of sync with the rates."""
    assert HYSA_BASELINE.annual_return == pytest.approx(0.045)
    assert MORTGAGE_PAYDOWN_BASELINE.annual_return == pytest.approx(0.06)
    assert SP500_BASELINE.annual_return == pytest.approx(0.07)
