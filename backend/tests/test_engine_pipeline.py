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
    ExportCreditInputs,
    FinancialInputs,
    ForecastInputs,
    SystemInputs,
    TariffInputs,
)
from backend.engine.pipeline import ENGINE_STEP_ORDER, ForecastResult, run_forecast
from backend.engine.steps.dc_production import DcProductionResult
from backend.engine.steps.degradation import DegradationCurve
from backend.engine.steps.export_credit import ExportCreditResult
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
    export_credit: ExportCreditInputs | None = None,
    consumption: ConsumptionInputs | None = None,
    hold_years: int = 25,
) -> ForecastInputs:
    return ForecastInputs(
        system=SystemInputs(lat=33.45, lon=-112.07, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(hold_years=hold_years),
        tariff=TariffInputs(country="US", schedule=schedule, export_credit=export_credit),
        consumption=consumption,
    )


def test_canonical_step_order_matches_phase_1a_pipeline() -> None:
    # Order matters: dc_production must come before degradation (degradation
    # reads hold_years off financial inputs but its result feeds tariff
    # year-1 vs year-N math), and tariff must come before export_credit
    # (the latter consumes the same net-load shape).
    expected = (
        "engine.irradiance",
        "engine.consumption",
        "engine.dc_production",
        "engine.degradation",
        "engine.tariff",
        "engine.export_credit",
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
    export = ExportCreditInputs(regime="seg_flat", flat_rate_per_kwh=0.05)
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
    export = ExportCreditInputs(regime="seg_flat", flat_rate_per_kwh=0.05)
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


def test_pipeline_artifacts_only_carry_step_outputs() -> None:
    """The pipeline must not leak intermediate derived series (net load,
    hourly export) into ``artifacts``. Those are private to the
    tariff and export-credit adapters; exposing them invites callers
    to depend on plumbing details that should stay free to refactor."""
    schedule = _flat_tariff()
    export = ExportCreditInputs(regime="seg_flat", flat_rate_per_kwh=0.05)
    inputs = _baseline_inputs(schedule=schedule, export_credit=export)
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)

    result = run_forecast(inputs, tmy=tmy)

    assert "engine.net_load" not in result.artifacts
    assert "engine.hourly_export_kwh" not in result.artifacts
    # The step outputs themselves still land where the public contract says.
    assert "engine.tariff" in result.artifacts
    assert "engine.export_credit" in result.artifacts
