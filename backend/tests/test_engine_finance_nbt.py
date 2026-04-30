"""engine.finance × NBT integration."""

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
from backend.engine.pipeline import run_forecast
from backend.engine.steps.finance import FinanceResult
from backend.providers.fake import synthetic_tmy
from backend.providers.irradiance import HOURS_PER_TMY
from backend.providers.tariff import TariffSchedule

#: Big system, tiny load — forces the within-month cap to bind and the
#: year-end zero-out to cut off surplus credit on every test fixture.
_FIXTURE_FLAT_RATE = 0.30
_FIXTURE_FIXED_MONTHLY = 10.0
_FIXTURE_CONSUMPTION_KWH = 2_000.0
_FIXTURE_DC_KW = 15.0
_FIXTURE_HOLD_YEARS = 5


def _flat_tariff() -> TariffSchedule:
    return TariffSchedule(
        name="cpuc-test",
        utility="pge",
        country="US",
        currency="USD",
        structure="flat",
        fixed_monthly_charge=_FIXTURE_FIXED_MONTHLY,
        flat_rate_per_kwh=_FIXTURE_FLAT_RATE,
    )


def _inputs(*, export_credit: ExportCreditInputs) -> ForecastInputs:
    return ForecastInputs(
        system=SystemInputs(
            lat=33.45,
            lon=-112.07,
            dc_kw=_FIXTURE_DC_KW,
            tilt_deg=25,
            azimuth_deg=180,
        ),
        financial=FinancialInputs(
            hold_years=_FIXTURE_HOLD_YEARS,
            discount_rate=0.06,
            system_cost=30_000.0,
            annual_opex=0.0,
        ),
        tariff=TariffInputs(
            country="US",
            schedule=_flat_tariff(),
            export_credit=export_credit,
        ),
        consumption=ConsumptionInputs(annual_kwh=_FIXTURE_CONSUMPTION_KWH),
    )


def _run(export_credit: ExportCreditInputs) -> FinanceResult:
    inputs = _inputs(export_credit=export_credit)
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)
    finance = run_forecast(inputs, tmy=tmy).artifacts["engine.finance"]
    assert isinstance(finance, FinanceResult)
    return finance


def test_nbt_caps_credit_below_seg_tou_when_surplus_exceeds_import_bill() -> None:
    """Same hourly rates on both regimes: SEG-TOU pays the raw credit,
    NBT applies the within-month cap + year-end forfeit. NBT's per-year
    credit and NPV must come in strictly lower."""
    # Uniform $1/kWh export rate × big system × small load → surplus
    # vastly exceeds the bill, so the cap binds and forfeit happens.
    huge_rates = [1.0] * HOURS_PER_TMY

    nbt = _run(
        ExportCreditInputs(
            regime="nem_three_nbt",
            hourly_avoided_cost_per_kwh=huge_rates,
        )
    )
    seg = _run(
        ExportCreditInputs(
            regime="seg_tou",
            hourly_rate_per_kwh=huge_rates,
        )
    )

    # Bill avoidance is regime-agnostic — same import-side savings for
    # both runs (same consumption, same production, same tariff).
    assert nbt.bill_avoidance_per_year == pytest.approx(seg.bill_avoidance_per_year)

    # NBT credit per year is strictly smaller — the cap on energy_charge +
    # year-end zero-out forfeits the bulk of the raw credit.
    for nbt_yr, seg_yr in zip(nbt.export_credit_per_year, seg.export_credit_per_year, strict=True):
        assert nbt_yr < seg_yr

    # NPV moves accordingly: same year-0 capex, same bill avoidance,
    # smaller credit on NBT → smaller NPV.
    assert nbt.npv < seg.npv


def test_nbt_credit_per_year_is_bounded_by_with_solar_energy_charge() -> None:
    """CPUC NBT caps credit at the energy portion of each month's bill;
    rolled up annually, applied credit can't exceed the with-solar
    bill's annual energy charge."""
    rates = [0.30] * HOURS_PER_TMY
    finance = _run(
        ExportCreditInputs(
            regime="nem_three_nbt",
            hourly_avoided_cost_per_kwh=rates,
        )
    )

    # The flat tariff makes baseline energy = consumption × rate; the
    # with-solar energy charge is what's left after bill avoidance.
    # The fixed monthly charge cancels in the bill_avoidance subtraction.
    baseline_energy = _FIXTURE_CONSUMPTION_KWH * _FIXTURE_FLAT_RATE
    for credit_yr, avoidance_yr in zip(
        finance.export_credit_per_year,
        finance.bill_avoidance_per_year,
        strict=True,
    ):
        with_solar_energy = baseline_energy - avoidance_yr
        assert 0 <= credit_yr <= with_solar_energy + 1e-6


def test_nem_one_for_one_regime_is_unaffected_by_nbt_branch() -> None:
    """Regression guard — NEM 1:1 must skip the NBT cap path."""
    finance = _run(ExportCreditInputs(regime="nem_one_for_one"))
    assert any(c > 0 for c in finance.export_credit_per_year)
    assert finance.npv > 0.0


def test_seg_flat_regime_is_unaffected_by_nbt_branch() -> None:
    """Regression guard — SEG-flat pays cash; no within-month netting."""
    finance = _run(ExportCreditInputs(regime="seg_flat", flat_rate_per_kwh=0.05))
    assert any(c > 0 for c in finance.export_credit_per_year)
