"""Financial roll-up: loans, NPV / IRR / MIRR / payback / LCOE / crossover.

Composes the pure-math primitives in ``backend.engine.finance`` against
the upstream pipeline state. The orchestration is:

* Year-1 production from ``engine.dc_production`` is scaled by the
  ``engine.degradation`` curve to give per-year AC kWh.
* For each year, hourly net load is recomputed against the degraded
  production and re-billed through the tariff step's primitives — bill
  avoidance is ``baseline_no_solar_bill - with_solar_bill_year_t``.
  Re-billing per year is exact (handles tiered + TOU rates correctly,
  not just flat); the cost is N×O(8760) which is cheap relative to the
  pvlib ModelChain run upstream.
* Export credit is recomputed per year against the same degraded
  production stream.
* The annual cashflow is ``bill_avoidance + export_credit − annual_opex
  − annual_loan_payment``. Year 0 is ``-system_cost`` for cash buys, or
  ``-down_payment`` when a loan is provided.
* NPV / IRR / MIRR / discounted payback / LCOE / crossover year are
  derived from that cashflow stream + the per-year energy curve.

The step is intentionally pure: no provider calls, no IO. It re-uses
the registered tariff + export-credit primitives by importing the
public functions, which keeps the orchestration honest — tomorrow's
``IncentiveProvider`` integration drops in by extending year-0 with
tax credits and rebates.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.engine.finance import (
    AmortizationSchedule,
    amortize,
    crossover_year,
    discounted_payback_years,
    irr,
    lcoe,
    mirr,
    npv,
)
from backend.engine.inputs import (
    ExportCreditInputs,
    FinancialInputs,
    LoanInputs,
)
from backend.engine.integration.nbt import compute_nbt_net_bill
from backend.engine.registry import register
from backend.engine.steps.dc_production import DcProductionResult
from backend.engine.steps.degradation import DegradationCurve
from backend.engine.steps.export_credit import apply_export_credit
from backend.engine.steps.tariff import compute_annual_bill
from backend.providers.irradiance import HOURS_PER_TMY
from backend.providers.tariff import TariffSchedule


class FinanceResult(BaseModel):
    """Headline finance numbers + per-year cashflow stream.

    ``per_year_cashflow[0]`` is year-0 capex (negative, sign-conventioned
    as the homeowner experiences it); ``per_year_cashflow[t]`` for
    ``t >= 1`` is the net of bill avoidance + export credit − opex −
    loan payments.

    ``irr`` / ``mirr`` / ``discounted_payback_years`` / ``crossover_year``
    are ``None`` when the underlying math is undefined (no sign change
    in the cashflow stream, never reaches break-even, etc.) — callers
    render those as "won't pay back at this discount rate" rather than
    crashing the audit.
    """

    per_year_cashflow: list[float]
    bill_avoidance_per_year: list[float]
    export_credit_per_year: list[float]
    energy_kwh_per_year: list[float]
    npv: float
    irr: float | None
    mirr: float | None
    discounted_payback_years: float | None
    lcoe: float
    crossover_year: int | None
    monthly_loan_payments: list[float] = Field(default_factory=list)


def _net_load_for_year(
    *,
    consumption: list[float],
    hourly_ac_kw: list[float],
    degradation_factor: float,
) -> list[float]:
    """Hourly grid net load with production scaled by ``degradation_factor``.

    Positive entries are imports, negative are exports. The factor scales
    each hour's production uniformly — solar degradation is a capacity
    derate, not a shape change.
    """
    return [c - p * degradation_factor for c, p in zip(consumption, hourly_ac_kw, strict=True)]


def _hourly_export(net_load: list[float]) -> list[float]:
    return [max(0.0, -nl) for nl in net_load]


def _finance_year_terms(
    *,
    baseline_total: float,
    consumption: list[float],
    hourly_ac_kw: list[float],
    degradation_factor: float,
    schedule: TariffSchedule,
    export_config: ExportCreditInputs | None,
) -> tuple[float, float]:
    """One year's (bill_avoidance, export_credit_dollars).

    Bill avoidance is always the import-side delta
    ``baseline_total − with_solar_bill.annual_total`` — the money the
    homeowner doesn't pay because solar covers part of the load.
    Export credit is the cash returned for kWh that crossed the meter
    outbound; the per-regime cap rules live in this branch.

    Under NEM 3.0 / NBT the raw credit overstates: CPUC caps
    within-month credit at the energy portion of that month's bill,
    rolls surplus forward, and zeros out unused surplus at year-end.
    ``compute_nbt_net_bill`` enforces those rules; we report the
    ``annual_credit_applied`` slice — the part that actually reduced
    bills — and let the unused surplus quietly forfeit. Bill
    avoidance is unchanged across regimes; the regime-specific math
    lives entirely on the credit line, which keeps cashflow
    composition (``bill_avoidance + export_credit − opex − debt``)
    uniform.

    NEM 1:1 and SEG-flat / SEG-TOU keep the raw annual credit:
    NEM 1:1's retail-rate credit is by construction always usable
    against same-month consumption, and SEG regimes settle in cash
    rather than against the import bill.
    """
    net_load = _net_load_for_year(
        consumption=consumption,
        hourly_ac_kw=hourly_ac_kw,
        degradation_factor=degradation_factor,
    )
    with_solar_bill = compute_annual_bill(hourly_net_load_kwh=net_load, tariff=schedule)
    bill_avoidance = baseline_total - with_solar_bill.annual_total

    if export_config is None:
        return bill_avoidance, 0.0

    credit = apply_export_credit(
        regime=export_config.regime,
        hourly_export_kwh=_hourly_export(net_load),
        tariff=schedule,
        hourly_avoided_cost_per_kwh=export_config.hourly_avoided_cost_per_kwh,
        rate_per_kwh=export_config.flat_rate_per_kwh,
        hourly_rate_per_kwh=export_config.hourly_rate_per_kwh,
    )

    if export_config.regime == "nem_three_nbt":
        netted = compute_nbt_net_bill(annual_bill=with_solar_bill, export_credit=credit)
        return bill_avoidance, netted.annual_credit_applied

    return bill_avoidance, credit.annual_credit


def _annual_loan_payments(loan: LoanInputs, hold_years: int) -> tuple[list[float], list[float]]:
    """(monthly_schedule, per-year debt service over ``hold_years``).

    ``per_year`` carries the sum of each year's twelve payments, padded
    with zeros once the loan is paid off. When ``term_months`` exceeds
    ``hold_years × 12``, the homeowner is still paying after the
    analysis horizon — that residual debt isn't a year-N inflow problem
    for this step (the audit can flag the post-horizon balance
    separately).
    """
    schedule: AmortizationSchedule = amortize(
        principal=loan.principal,
        apr=loan.apr,
        term_months=loan.term_months,
    )
    monthly = [row.payment for row in schedule.rows]
    per_year: list[float] = []
    for year in range(hold_years):
        start = year * 12
        end = start + 12
        per_year.append(sum(monthly[start:end]))
    return monthly, per_year


def _starting_utility_rate(baseline_kwh: float, baseline_energy_charge: float) -> float | None:
    """Average $/kWh on the no-solar baseline bill — used as the starting
    point for the crossover-year calculation. Returns ``None`` when the
    household has zero baseline imports (degenerate; no rate to escalate)."""
    if baseline_kwh <= 0.0:
        return None
    return baseline_energy_charge / baseline_kwh


def _safe_irr(cashflows: list[float]) -> float | None:
    try:
        return irr(cashflows)
    except ValueError:
        return None


def _safe_mirr(
    cashflows: list[float],
    *,
    finance_rate: float,
    reinvest_rate: float,
) -> float | None:
    try:
        return mirr(cashflows, finance_rate=finance_rate, reinvest_rate=reinvest_rate)
    except ValueError:
        return None


@register("engine.finance")
def run_finance(
    *,
    financial: FinancialInputs,
    consumption: list[float],
    dc: DcProductionResult,
    degradation: DegradationCurve,
    schedule: TariffSchedule,
    export_credit: ExportCreditInputs | None = None,
) -> FinanceResult:
    """Compose the per-year cashflow stream and headline metrics.

    Requires a tariff schedule — bill avoidance is the dominant term in
    residential solar's NPV, so a finance run without one would be a
    misleading half-answer. Export-credit input is optional; without it
    the model assumes the regime contributes zero (technically wrong for
    SEG-flat households, but the absence of an ``ExportCreditInputs`` is
    the caller's signal that they don't want export credit accounted
    for).
    """
    if financial.system_cost is None:
        raise ValueError("system_cost is required to run engine.finance")
    if len(consumption) != HOURS_PER_TMY:
        raise ValueError(f"consumption must be {HOURS_PER_TMY} entries (got {len(consumption)})")
    if len(degradation.factors) < financial.hold_years:
        raise ValueError(
            f"degradation curve has {len(degradation.factors)} years but "
            f"hold_years is {financial.hold_years}"
        )

    baseline = compute_annual_bill(hourly_net_load_kwh=consumption, tariff=schedule)

    bill_avoidance: list[float] = []
    export_credits: list[float] = []
    energy_per_year: list[float] = []

    for year in range(financial.hold_years):
        factor = degradation.factors[year]
        avoidance, year_export_credit = _finance_year_terms(
            baseline_total=baseline.annual_total,
            consumption=consumption,
            hourly_ac_kw=dc.hourly_ac_kw,
            degradation_factor=factor,
            schedule=schedule,
            export_config=export_credit,
        )
        bill_avoidance.append(avoidance)
        export_credits.append(year_export_credit)
        energy_per_year.append(dc.annual_ac_kwh * factor)

    monthly_loan_payments: list[float] = []
    per_year_loan_payment: list[float] = [0.0] * financial.hold_years
    if financial.loan is not None:
        monthly_loan_payments, per_year_loan_payment = _annual_loan_payments(
            financial.loan, financial.hold_years
        )

    year_zero = -(
        financial.loan.down_payment if financial.loan is not None else financial.system_cost
    )
    cashflows = [year_zero]
    for year in range(financial.hold_years):
        cashflows.append(
            bill_avoidance[year]
            + export_credits[year]
            - financial.annual_opex
            - per_year_loan_payment[year]
        )

    project_lcoe = lcoe(
        capex=financial.system_cost,
        opex_per_year=[financial.annual_opex] * financial.hold_years,
        energy_kwh_per_year=energy_per_year,
        discount_rate=financial.discount_rate,
    )

    starting_rate = _starting_utility_rate(
        baseline.annual_kwh_imported, baseline.annual_energy_charge
    )
    crossover = (
        crossover_year(
            lcoe_per_kwh=project_lcoe,
            starting_utility_rate_per_kwh=starting_rate,
            rate_escalation=financial.rate_escalation,
            horizon_years=financial.hold_years,
        )
        if starting_rate is not None
        else None
    )

    return FinanceResult(
        per_year_cashflow=cashflows,
        bill_avoidance_per_year=bill_avoidance,
        export_credit_per_year=export_credits,
        energy_kwh_per_year=energy_per_year,
        npv=npv(financial.discount_rate, cashflows),
        irr=_safe_irr(cashflows),
        mirr=_safe_mirr(
            cashflows,
            finance_rate=financial.discount_rate,
            reinvest_rate=financial.discount_rate,
        ),
        discounted_payback_years=discounted_payback_years(financial.discount_rate, cashflows),
        lcoe=project_lcoe,
        crossover_year=crossover,
        monthly_loan_payments=monthly_loan_payments,
    )
