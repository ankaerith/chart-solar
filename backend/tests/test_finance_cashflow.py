"""NPV / IRR / MIRR / discounted payback / LCOE pure-math tests.

Most assertions cross-check against numpy-financial-style closed-form
references; we don't depend on numpy-financial in the runtime (pulls
extra weight + has a deprecation history with NumPy 2.x), so the
reference math is inlined here.
"""

from __future__ import annotations

import math

import pytest

from backend.engine.finance import (
    annualized_return,
    crossover_year,
    discounted_payback_years,
    irr,
    lcoe,
    mirr,
    npv,
)


def test_npv_zero_rate_is_simple_sum() -> None:
    assert npv(0.0, [-100.0, 50.0, 50.0, 50.0]) == pytest.approx(50.0)


def test_npv_positive_rate_discounts_future_inflows() -> None:
    flows = [-1000.0, 400.0, 400.0, 400.0]
    expected = -1000.0 + 400.0 / 1.10 + 400.0 / 1.10**2 + 400.0 / 1.10**3
    assert npv(0.10, flows) == pytest.approx(expected)


def test_npv_year_zero_undiscounted() -> None:
    """Year 0 cashflow is *not* discounted — it's "today's dollars"."""
    flows = [100.0]
    assert npv(0.5, flows) == pytest.approx(100.0)


def test_npv_negative_rate_inflates_future() -> None:
    """Real-rate scenarios (TIPS, deflation) — math should still work."""
    flows = [-100.0, 50.0, 50.0]
    assert npv(-0.05, flows) > 0.0


def test_npv_rejects_empty_cashflows() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        npv(0.05, [])


def test_npv_rejects_rate_at_minus_one() -> None:
    with pytest.raises(ValueError, match="> -1.0"):
        npv(-1.0, [-100.0, 50.0])


def test_irr_classic_solar_stream_matches_expected() -> None:
    """A 25k system saving 2.5k/yr for 25 years has IRR ≈ 9.7 %."""
    flows = [-25_000.0] + [2_500.0] * 25
    rate = irr(flows)
    assert npv(rate, flows) == pytest.approx(0.0, abs=1e-4)
    assert 0.08 < rate < 0.11


def test_irr_zero_npv_at_solution() -> None:
    """The defining property: NPV at IRR is zero."""
    flows = [-10_000.0, 3_000.0, 4_200.0, 6_800.0]
    rate = irr(flows)
    assert npv(rate, flows) == pytest.approx(0.0, abs=1e-6)


def test_irr_handles_short_two_period_stream() -> None:
    flows = [-100.0, 110.0]
    assert irr(flows) == pytest.approx(0.10, abs=1e-6)


def test_irr_rejects_all_positive_stream() -> None:
    with pytest.raises(ValueError, match="positive and one negative"):
        irr([100.0, 100.0, 100.0])


def test_irr_rejects_all_negative_stream() -> None:
    with pytest.raises(ValueError, match="positive and one negative"):
        irr([-100.0, -100.0, -100.0])


def test_irr_rejects_empty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        irr([])


def test_mirr_with_equal_rates_approaches_irr() -> None:
    """When finance + reinvest rates equal IRR, MIRR == IRR — the
    classic identity."""
    flows = [-25_000.0] + [2_500.0] * 25
    project_irr = irr(flows)
    project_mirr = mirr(flows, finance_rate=project_irr, reinvest_rate=project_irr)
    assert project_mirr == pytest.approx(project_irr, abs=1e-4)


def test_mirr_lower_reinvest_rate_lowers_mirr() -> None:
    """Reinvesting savings at 4 % instead of the project's IRR drops
    MIRR — the whole point of MIRR is calling that out."""
    flows = [-25_000.0] + [2_500.0] * 25
    realistic_mirr = mirr(flows, finance_rate=0.06, reinvest_rate=0.04)
    project_irr = irr(flows)
    assert realistic_mirr < project_irr


def test_mirr_textbook_example() -> None:
    """Cross-checked against the Excel/numpy-financial MIRR formula."""
    flows = [-1000.0, 200.0, 300.0, 400.0, 500.0]
    finance_rate, reinvest_rate = 0.10, 0.12
    n = len(flows) - 1
    pv_out = -1000.0 / (1.0 + finance_rate) ** 0
    fv_in = 200.0 * 1.12**3 + 300.0 * 1.12**2 + 400.0 * 1.12**1 + 500.0 * 1.12**0
    expected = (fv_in / -pv_out) ** (1.0 / n) - 1.0
    assert mirr(flows, finance_rate=finance_rate, reinvest_rate=reinvest_rate) == pytest.approx(
        expected
    )


def test_mirr_rejects_short_stream() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        mirr([-100.0], finance_rate=0.05, reinvest_rate=0.05)


def test_mirr_rejects_all_positive() -> None:
    with pytest.raises(ValueError, match="positive and negative"):
        mirr([100.0, 100.0, 100.0], finance_rate=0.05, reinvest_rate=0.05)


def test_discounted_payback_simple_case() -> None:
    """Year 1 alone clears year-0 outflow at 0 % discount: payback = 1."""
    assert discounted_payback_years(0.0, [-100.0, 100.0]) == pytest.approx(1.0)


def test_discounted_payback_interpolates_within_year() -> None:
    """Year 0 outflow 100, year 1 inflow 50, year 2 inflow 50 at 0 %:
    cumulative is -100, -50, 0 — payback exactly at year 2."""
    assert discounted_payback_years(0.0, [-100.0, 50.0, 50.0]) == pytest.approx(2.0)


def test_discounted_payback_fractional_year() -> None:
    """Year 0 outflow 100, year 1 inflow 30, year 2 inflow 100 at 0 %:
    cumulative -100, -70, +30. Crosses inside year 2 at 70 % through."""
    flows = [-100.0, 30.0, 100.0]
    payback = discounted_payback_years(0.0, flows)
    assert payback is not None
    assert payback == pytest.approx(1.0 + 0.7, abs=1e-6)


def test_discounted_payback_higher_rate_pushes_payback_later() -> None:
    flows = [-25_000.0] + [2_500.0] * 25
    low_rate = discounted_payback_years(0.03, flows)
    high_rate = discounted_payback_years(0.08, flows)
    assert low_rate is not None and high_rate is not None
    assert high_rate > low_rate


def test_discounted_payback_returns_none_when_never_breaks_even() -> None:
    """Tiny annual savings at a high discount rate: discounted total
    never catches up to the year-0 outflow."""
    flows = [-100_000.0] + [1_000.0] * 25
    assert discounted_payback_years(0.10, flows) is None


def test_discounted_payback_year_zero_already_positive() -> None:
    """Edge case: year 0 is itself non-negative — payback is 0."""
    assert discounted_payback_years(0.05, [0.0, 100.0]) == pytest.approx(0.0)


def test_discounted_payback_rejects_empty() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        discounted_payback_years(0.05, [])


def test_lcoe_no_opex_zero_discount_is_capex_over_total_kwh() -> None:
    """At 0 % discount with no opex, LCOE collapses to total cost
    over total energy."""
    assert lcoe(
        capex=10_000.0,
        opex_per_year=[0.0] * 25,
        energy_kwh_per_year=[10_000.0] * 25,
        discount_rate=0.0,
    ) == pytest.approx(10_000.0 / (10_000.0 * 25))


def test_lcoe_realistic_residential_solar_in_expected_range() -> None:
    """Typical 8 kW system, ~$2.50/W, 25-yr life, 0.5 %/yr deg.

    LCOE depends heavily on discount-rate choice — at 0 % it lands
    around 9 ¢ (the popular "solar is cheap" framing); at 6 % it
    pushes to ~16 ¢ once future kWh are time-discounted. We pin the
    0 % case as the audit's "pre-finance" headline value.
    """
    capex = 8.0 * 1000.0 * 2.50
    opex = [80.0] * 25
    base_kwh = 8.0 * 1300.0
    energy = [base_kwh * (1.0 - 0.005 * t) for t in range(25)]
    pre_finance = lcoe(
        capex=capex,
        opex_per_year=opex,
        energy_kwh_per_year=energy,
        discount_rate=0.0,
    )
    real_rate = lcoe(
        capex=capex,
        opex_per_year=opex,
        energy_kwh_per_year=energy,
        discount_rate=0.06,
    )
    assert 0.07 < pre_finance < 0.10
    assert 0.13 < real_rate < 0.20


def test_lcoe_higher_discount_rate_raises_lcoe() -> None:
    """At higher discount rates, future kWh discount faster than
    future opex (because year-0 capex dominates the numerator) — so
    LCOE rises."""
    base = lcoe(
        capex=20_000.0,
        opex_per_year=[100.0] * 25,
        energy_kwh_per_year=[10_000.0] * 25,
        discount_rate=0.03,
    )
    higher = lcoe(
        capex=20_000.0,
        opex_per_year=[100.0] * 25,
        energy_kwh_per_year=[10_000.0] * 25,
        discount_rate=0.10,
    )
    assert higher > base


def test_lcoe_rejects_misaligned_streams() -> None:
    with pytest.raises(ValueError, match="must align"):
        lcoe(
            capex=1.0,
            opex_per_year=[0.0, 0.0],
            energy_kwh_per_year=[1.0, 1.0, 1.0],
            discount_rate=0.05,
        )


def test_lcoe_rejects_negative_capex() -> None:
    with pytest.raises(ValueError, match="capex must be >= 0"):
        lcoe(
            capex=-1.0,
            opex_per_year=[0.0],
            energy_kwh_per_year=[1.0],
            discount_rate=0.05,
        )


def test_lcoe_rejects_zero_energy() -> None:
    with pytest.raises(ValueError, match="energy must be > 0"):
        lcoe(
            capex=1.0,
            opex_per_year=[0.0, 0.0],
            energy_kwh_per_year=[0.0, 0.0],
            discount_rate=0.05,
        )


def test_crossover_year_returns_year_when_rate_passes_lcoe() -> None:
    """LCOE 8 ¢, utility starts at 6 ¢, escalates 5 %/yr → crosses
    around year 6 (1.05^5 = 1.276; 6 * 1.276 = 7.66; year 7 is first
    above 8)."""
    year = crossover_year(
        lcoe_per_kwh=0.08,
        starting_utility_rate_per_kwh=0.06,
        rate_escalation=0.05,
        horizon_years=25,
    )
    assert year == 7


def test_crossover_year_year_one_when_already_above() -> None:
    year = crossover_year(
        lcoe_per_kwh=0.05,
        starting_utility_rate_per_kwh=0.10,
        rate_escalation=0.03,
        horizon_years=25,
    )
    assert year == 1


def test_crossover_year_none_when_never_crosses() -> None:
    """LCOE 50 ¢, utility starts at 5 ¢ with low escalation → never
    crosses inside 25 years."""
    year = crossover_year(
        lcoe_per_kwh=0.50,
        starting_utility_rate_per_kwh=0.05,
        rate_escalation=0.02,
        horizon_years=25,
    )
    assert year is None


def test_crossover_year_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        crossover_year(
            lcoe_per_kwh=-0.01,
            starting_utility_rate_per_kwh=0.10,
            rate_escalation=0.03,
            horizon_years=25,
        )
    with pytest.raises(ValueError):
        crossover_year(
            lcoe_per_kwh=0.10,
            starting_utility_rate_per_kwh=0.10,
            rate_escalation=0.03,
            horizon_years=0,
        )


def test_annualized_return_simple_doubling() -> None:
    """100 in, 200 out at year 5 with 0 % discount → ~14.87 %/yr
    geometric growth (2 ^ (1/5) - 1)."""
    flows = [-100.0, 0.0, 0.0, 0.0, 0.0, 200.0]
    rate = annualized_return(flows, discount_rate=0.0)
    expected = math.pow(2.0, 1.0 / 5.0) - 1.0
    assert rate == pytest.approx(expected, abs=1e-6)


def test_annualized_return_negative_when_no_inflows() -> None:
    """Pure outflow stream → -100 %/yr signal; caller renders as 'no
    return' rather than an actual rate."""
    flows = [-100.0, -10.0, -10.0]
    assert annualized_return(flows, discount_rate=0.05) == pytest.approx(-1.0)
