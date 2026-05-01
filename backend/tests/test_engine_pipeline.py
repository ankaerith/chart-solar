"""End-to-end pipeline composition.

Covers chart-solar-cm4i: the pipeline walks ENGINE_STEP_ORDER, dispatches
each registered step through its adapter, and produces a ForecastResult
whose `artifacts` dict carries each step's output keyed by feature key.

These tests use the synthetic clear-sky TMY (no network IO) plus a fully
configured TariffInputs so the full chain — dc_production → degradation
→ tariff → export_credit — actually runs end-to-end. Mid-chain skips
(no schedule, no export config) are tested separately so the degraded
shape is also covered.
"""

from __future__ import annotations

import pytest

from backend.engine.inputs import (
    ConsumptionInputs,
    ExportCreditConfig,
    FinancialInputs,
    ForecastInputs,
    LoanInputs,
    NemOneForOneConfig,
    SegFlatConfig,
    SystemInputs,
    TariffInputs,
)
from backend.engine.pipeline import ENGINE_STEP_ORDER, ForecastResult, run_forecast
from backend.engine.steps.dc_production import DcProductionResult
from backend.engine.steps.degradation import DegradationCurve
from backend.engine.steps.export_credit import ExportCreditResult
from backend.engine.steps.finance import FinanceResult
from backend.engine.steps.tariff import AnnualBill
from backend.providers.fake import synthetic_tmy
from backend.providers.irradiance import HOURS_PER_TMY
from backend.providers.tariff import TariffSchedule


def _flat_tariff(rate: float = 0.16, fixed: float = 10.0) -> TariffSchedule:
    return TariffSchedule(
        name="test flat",
        utility="test-util",
        country="US",
        currency="USD",
        structure="flat",
        fixed_monthly_charge=fixed,
        flat_rate_per_kwh=rate,
    )


def _baseline_inputs(
    *,
    schedule: TariffSchedule | None = None,
    export_credit: ExportCreditConfig | None = None,
    consumption: ConsumptionInputs | None = None,
    hold_years: int = 25,
    financial: FinancialInputs | None = None,
) -> ForecastInputs:
    return ForecastInputs(
        system=SystemInputs(lat=33.45, lon=-112.07, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=financial if financial is not None else FinancialInputs(hold_years=hold_years),
        tariff=TariffInputs(country="US", schedule=schedule, export_credit=export_credit),
        consumption=consumption,
    )


def test_canonical_step_order_matches_phase_1a_pipeline() -> None:
    # Order matters: dc_production must come before degradation (degradation
    # reads hold_years off financial inputs but its result feeds tariff
    # year-1 vs year-N math); tariff must come before export_credit (the
    # latter consumes the same net-load shape); finance comes last because
    # it composes every prior artifact into per-year cashflow + headlines.
    expected = (
        "engine.irradiance",
        "engine.consumption",
        "engine.dc_production",
        "engine.degradation",
        "engine.tariff",
        "engine.export_credit",
        "engine.finance",
    )
    assert ENGINE_STEP_ORDER == expected


def test_pipeline_runs_dc_and_degradation_without_a_tariff_schedule() -> None:
    inputs = _baseline_inputs()
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)
    result = run_forecast(inputs, tmy=tmy)

    assert isinstance(result, ForecastResult)
    assert result.artifacts["engine.irradiance"] is tmy

    dc = result.artifacts["engine.dc_production"]
    assert isinstance(dc, DcProductionResult)
    assert dc.annual_ac_kwh > 0.0
    assert len(dc.hourly_ac_kw) == HOURS_PER_TMY

    curve = result.artifacts["engine.degradation"]
    assert isinstance(curve, DegradationCurve)
    assert len(curve.factors) == inputs.financial.hold_years

    # Tariff + export-credit are skipped silently when their inputs are absent.
    assert "engine.tariff" not in result.artifacts
    assert "engine.export_credit" not in result.artifacts


def test_pipeline_bills_a_household_with_zero_consumption_at_the_fixed_charge() -> None:
    """No consumption ⇒ every produced kWh exports ⇒ billed import is 0;
    the bill collapses to twelve fixed-charge months. This is the simplest
    end-to-end path that exercises the tariff adapter."""
    schedule = _flat_tariff(rate=0.20, fixed=10.0)
    inputs = _baseline_inputs(schedule=schedule)
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(inputs, tmy=tmy)

    bill = result.artifacts["engine.tariff"]
    assert isinstance(bill, AnnualBill)
    assert bill.annual_kwh_imported == 0.0
    assert bill.annual_energy_charge == 0.0
    assert bill.annual_fixed_charge == pytest.approx(10.0 * 12)
    assert bill.annual_total == pytest.approx(10.0 * 12)


def test_pipeline_credits_seg_flat_export_when_consumption_is_zero() -> None:
    """SEG-flat: every exported kWh credits at a single rate. With zero
    consumption, exported kWh ≈ produced kWh, so annual credit ≈ AC yield × rate."""
    schedule = _flat_tariff(rate=0.16, fixed=10.0)
    export = SegFlatConfig(flat_rate_per_kwh=0.05)
    inputs = _baseline_inputs(schedule=schedule, export_credit=export)
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(inputs, tmy=tmy)

    dc: DcProductionResult = result.artifacts["engine.dc_production"]
    credit = result.artifacts["engine.export_credit"]
    assert isinstance(credit, ExportCreditResult)
    assert credit.regime == "seg_flat"
    assert credit.annual_kwh_exported == pytest.approx(dc.annual_ac_kwh, rel=1e-9)
    assert credit.annual_credit == pytest.approx(dc.annual_ac_kwh * 0.05, rel=1e-9)


def test_pipeline_uses_consumption_when_provided() -> None:
    """A non-zero consumption profile reduces exported kWh below total
    production — the tariff bill grows with imported kWh, the export
    credit shrinks. The point of this test is the wiring: net load
    flows from consumption + dc_production into the tariff and
    export-credit adapters in lock-step."""
    even_load = ConsumptionInputs(annual_kwh=12_000.0)
    schedule = _flat_tariff(rate=0.20, fixed=10.0)
    export = SegFlatConfig(flat_rate_per_kwh=0.05)
    inputs = _baseline_inputs(
        schedule=schedule,
        export_credit=export,
        consumption=even_load,
    )
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(inputs, tmy=tmy)

    dc: DcProductionResult = result.artifacts["engine.dc_production"]
    bill: AnnualBill = result.artifacts["engine.tariff"]
    credit: ExportCreditResult = result.artifacts["engine.export_credit"]

    # Kirchhoff-on-the-meter sanity: imported + (consumption - imports
    # taken from local production) = consumption; exported < production.
    assert bill.annual_kwh_imported > 0.0
    assert credit.annual_kwh_exported < dc.annual_ac_kwh
    # Bill's energy charge should reflect the imported kWh at flat rate.
    assert bill.annual_energy_charge == pytest.approx(bill.annual_kwh_imported * 0.20, rel=1e-9)


def test_pipeline_skips_steps_that_arent_in_the_requested_feature_set() -> None:
    schedule = _flat_tariff()
    inputs = _baseline_inputs(schedule=schedule)
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(
        inputs,
        tmy=tmy,
        feature_keys={"engine.irradiance", "engine.dc_production"},
    )

    assert "engine.dc_production" in result.artifacts
    # Degradation + tariff are registered, but not requested → not run.
    assert "engine.degradation" not in result.artifacts
    assert "engine.tariff" not in result.artifacts


def test_pipeline_runs_finance_for_a_realistic_residential_system() -> None:
    """Cash purchase, 8 kW Phoenix-ish system, 25-yr hold, NEM 1:1.

    The engine.finance step should land NPV / IRR / payback in the
    plausible band a residential audit produces: positive NPV at 6 %
    discount, IRR around 7-15 %, payback inside the hold window.
    """
    schedule = _flat_tariff(rate=0.18, fixed=10.0)
    export = NemOneForOneConfig()
    consumption = ConsumptionInputs(annual_kwh=11_000.0)
    financial = FinancialInputs(
        hold_years=25,
        discount_rate=0.06,
        system_cost=22_000.0,
        annual_opex=80.0,
        rate_escalation=0.03,
    )
    inputs = _baseline_inputs(
        schedule=schedule,
        export_credit=export,
        consumption=consumption,
        financial=financial,
    )
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(inputs, tmy=tmy)

    finance = result.artifacts["engine.finance"]
    assert isinstance(finance, FinanceResult)
    assert len(finance.per_year_cashflow) == 26  # year 0 + 25 years
    assert finance.per_year_cashflow[0] == pytest.approx(-22_000.0)
    # All operating-year cashflows should be positive: bill avoidance +
    # NEM 1:1 export credit easily clears $80/yr opex on a Phoenix system.
    assert all(cf > 0 for cf in finance.per_year_cashflow[1:])
    assert finance.npv > 0.0
    assert finance.irr is not None and 0.05 < finance.irr < 0.30
    assert finance.discounted_payback_years is not None
    assert 3.0 < finance.discounted_payback_years < 25.0
    assert 0.05 < finance.lcoe < 0.30
    assert finance.crossover_year is not None and 1 <= finance.crossover_year <= 25


def test_finance_step_skips_when_system_cost_is_absent() -> None:
    """The pipeline must run end-to-end without finance inputs — Phase
    1a smoke tests still go through tariff + export_credit without
    requiring system cost."""
    schedule = _flat_tariff()
    inputs = _baseline_inputs(schedule=schedule)
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(inputs, tmy=tmy)

    assert "engine.tariff" in result.artifacts
    assert "engine.finance" not in result.artifacts


def test_finance_step_skips_when_tariff_schedule_is_absent() -> None:
    """No schedule means no bill avoidance — finance can't produce a
    meaningful headline so it skips rather than half-answering."""
    financial = FinancialInputs(hold_years=15, system_cost=20_000.0)
    inputs = _baseline_inputs(financial=financial)
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(inputs, tmy=tmy)

    assert "engine.finance" not in result.artifacts


def test_finance_step_amortizes_a_loan_into_year_cashflows() -> None:
    """A financed system: year 0 is just the down payment; subsequent
    years deduct loan service from the cashflow."""
    schedule = _flat_tariff(rate=0.18)
    consumption = ConsumptionInputs(annual_kwh=11_000.0)
    financial = FinancialInputs(
        hold_years=25,
        discount_rate=0.06,
        system_cost=22_000.0,
        loan=LoanInputs(
            principal=20_000.0,
            apr=0.0699,
            term_months=240,
            down_payment=2_000.0,
        ),
    )
    inputs = _baseline_inputs(
        schedule=schedule,
        consumption=consumption,
        financial=financial,
    )
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(inputs, tmy=tmy)
    finance = result.artifacts["engine.finance"]
    assert isinstance(finance, FinanceResult)
    assert finance.per_year_cashflow[0] == pytest.approx(-2_000.0)
    assert len(finance.monthly_loan_payments) == 240
    # Years inside the loan term carry debt service; years past it don't.
    cash_with_loan = finance.per_year_cashflow[1]  # year 1 (loan active)
    cash_post_loan = finance.per_year_cashflow[-1]  # year 25 (loan paid off year 20)
    assert cash_post_loan > cash_with_loan


def test_finance_step_routes_variable_rate_loans_through_amortize_variable() -> None:
    """An ARM-style loan with a mid-term rate reset must produce a
    different per-month payment schedule than the fixed-rate
    equivalent at the starting rate. Pins the dispatch path through
    LoanInputs.monthly_rates → amortize_variable."""
    schedule = _flat_tariff(rate=0.18)
    consumption = ConsumptionInputs(annual_kwh=11_000.0)
    term_months = 240

    # 5/15 ARM: 5 years at 4%, then resets to 7% for the remaining 15.
    monthly_rates = (
        [0.04 / 12.0] * 60  # months 1–60
        + [0.07 / 12.0] * (term_months - 60)
    )
    arm_financial = FinancialInputs(
        hold_years=25,
        discount_rate=0.06,
        system_cost=22_000.0,
        loan=LoanInputs(
            principal=20_000.0,
            monthly_rates=monthly_rates,
            term_months=term_months,
            down_payment=2_000.0,
        ),
    )
    fixed_financial = FinancialInputs(
        hold_years=25,
        discount_rate=0.06,
        system_cost=22_000.0,
        loan=LoanInputs(
            principal=20_000.0,
            apr=0.04,
            term_months=term_months,
            down_payment=2_000.0,
        ),
    )

    inputs_arm = _baseline_inputs(
        schedule=schedule, consumption=consumption, financial=arm_financial
    )
    inputs_fixed = _baseline_inputs(
        schedule=schedule, consumption=consumption, financial=fixed_financial
    )
    tmy = synthetic_tmy(lat=inputs_arm.system.lat, lon=inputs_arm.system.lon)

    arm = run_forecast(inputs_arm, tmy=tmy).artifacts["engine.finance"]
    fixed = run_forecast(inputs_fixed, tmy=tmy).artifacts["engine.finance"]
    assert isinstance(arm, FinanceResult) and isinstance(fixed, FinanceResult)

    # Same first-month payment (both at 4%); divergence after the
    # reset at month 61.
    assert arm.monthly_loan_payments[0] == pytest.approx(fixed.monthly_loan_payments[0])
    assert arm.monthly_loan_payments[60] != pytest.approx(fixed.monthly_loan_payments[60])
    # Higher post-reset rate ⇒ ARM total interest > fixed-rate total.
    assert sum(arm.monthly_loan_payments) > sum(fixed.monthly_loan_payments)


def test_loan_inputs_rejects_both_apr_and_monthly_rates() -> None:
    """Exactly one rate form must be set; setting both is a config bug."""
    with pytest.raises(ValueError, match="exactly one"):
        LoanInputs(
            principal=10_000.0,
            apr=0.05,
            monthly_rates=[0.05 / 12.0] * 60,
            term_months=60,
        )


def test_loan_inputs_rejects_neither_apr_nor_monthly_rates() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        LoanInputs(principal=10_000.0, term_months=60)


def test_loan_inputs_rejects_monthly_rates_length_mismatch() -> None:
    with pytest.raises(ValueError, match="must equal term_months"):
        LoanInputs(
            principal=10_000.0,
            monthly_rates=[0.05 / 12.0] * 30,
            term_months=60,
        )


def test_pipeline_artifacts_only_carry_step_outputs() -> None:
    """The pipeline must not leak intermediate derived series (net load,
    hourly export) into ``artifacts``. Those are private to the
    tariff and export-credit adapters; exposing them invites callers
    to depend on plumbing details that should stay free to refactor."""
    schedule = _flat_tariff()
    export = SegFlatConfig(flat_rate_per_kwh=0.05)
    inputs = _baseline_inputs(schedule=schedule, export_credit=export)
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(inputs, tmy=tmy)

    assert "engine.net_load" not in result.artifacts
    assert "engine.hourly_export_kwh" not in result.artifacts
    # The step outputs themselves still land where the public contract says.
    assert "engine.tariff" in result.artifacts
    assert "engine.export_credit" in result.artifacts


def test_pipeline_writes_a_snapshot_artifact_with_tariff_and_inputs_hashes() -> None:
    """Every forecast carries an `engine.snapshot` pin so a saved run
    can prove what produced it. Hashes must be 64-hex (sha256), the
    irradiance source + fetched_at must mirror the TMY, and the engine
    + pvlib version pins must be set."""
    from backend.engine.snapshot import (
        Snapshot,
        current_engine_version,
        current_pvlib_version,
    )

    schedule = _flat_tariff()
    inputs = _baseline_inputs(schedule=schedule)
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(inputs, tmy=tmy)

    snapshot = result.artifacts["engine.snapshot"]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.engine_version == current_engine_version()
    assert snapshot.pvlib_version == current_pvlib_version()
    assert snapshot.irradiance_source == tmy.source
    assert snapshot.irradiance_fetched_at == tmy.fetched_at
    assert len(snapshot.tariff_hash) == 64
    assert len(snapshot.inputs_hash) == 64


def test_pipeline_snapshot_hashes_are_stable_across_runs_with_identical_inputs() -> None:
    """Same inputs + same tariff → same hashes across two pipeline
    invocations. This is the property the snapshot pin needs so a
    re-open can short-circuit the pipeline and serve the cached result."""
    schedule = _flat_tariff()
    inputs = _baseline_inputs(schedule=schedule)
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    a = run_forecast(inputs, tmy=tmy)
    b = run_forecast(inputs, tmy=tmy)

    assert a.artifacts["engine.snapshot"].matches(b.artifacts["engine.snapshot"])
    assert a.artifacts["engine.snapshot"].tariff_hash == b.artifacts["engine.snapshot"].tariff_hash
    assert a.artifacts["engine.snapshot"].inputs_hash == b.artifacts["engine.snapshot"].inputs_hash


def test_pipeline_snapshot_tariff_hash_changes_when_tariff_changes() -> None:
    """Same inputs but a different tariff → tariff_hash differs;
    inputs_hash also differs because the schedule sits inside inputs.
    Together that surfaces 'tariff changed since you saved this' diff
    (the headline scenario from chart-solar-you)."""
    a_inputs = _baseline_inputs(schedule=_flat_tariff(rate=0.16))
    b_inputs = _baseline_inputs(schedule=_flat_tariff(rate=0.21))
    tmy = synthetic_tmy(lat=a_inputs.system.lat, lon=a_inputs.system.lon)

    a = run_forecast(a_inputs, tmy=tmy)
    b = run_forecast(b_inputs, tmy=tmy)

    assert a.artifacts["engine.snapshot"].tariff_hash != b.artifacts["engine.snapshot"].tariff_hash
