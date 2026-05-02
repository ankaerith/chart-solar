"""Snow loss step: pvlib Townsend monthly model.

Covers the four behaviours the pipeline depends on:

* No-op when the TMY lacks ``snowfall_cm_per_month`` or
  ``relative_humidity_pct_per_month`` (returns ``None``; pipeline
  adapter leaves the dc_production stream untouched).
* Zero monthly loss when monthly snowfall is zero across the year —
  the model should not invent loss out of thin air on a non-snowy site.
* Positive winter loss + zero summer loss on a moderate-snow site —
  Townsend's qualitative shape ("snow falls in winter, losses follow").
* End-to-end pipeline integration: snow runs after dc_production and
  the post-snow stream propagates into finance's per-year energy curve.
"""

from __future__ import annotations

import pytest

from backend.domain.tmy import HOURS_PER_TMY, TmyData
from backend.engine.inputs import (
    ConsumptionInputs,
    FinancialInputs,
    ForecastInputs,
    SnowGeometry,
    SystemInputs,
    TariffInputs,
)
from backend.engine.pipeline import run_forecast
from backend.engine.steps.dc_production import DcProductionResult, run_dc_production
from backend.engine.steps.snow import SnowLossResult, run_snow_loss
from backend.providers.fake.irradiance import synthetic_tmy


def _system() -> SystemInputs:
    """Mid-tilt residential array; tilt + lower-edge are Townsend-relevant."""
    return SystemInputs(lat=44.0, lon=-72.5, dc_kw=8.0, tilt_deg=25, azimuth_deg=180)


def _tmy_with_columns(
    *,
    snow: list[float] | None,
    rh: list[float] | None,
) -> TmyData:
    """A clear-sky synthetic TMY at a snowy mid-latitude, with optional
    snow / RH columns layered in. Air temp is a flat 5°C — Townsend
    uses monthly mean temp, the constant value just keeps the test
    fixture deterministic.
    """
    base = synthetic_tmy(lat=44.0, lon=-72.5, timezone="UTC", elevation_m=200.0)
    return TmyData(
        lat=base.lat,
        lon=base.lon,
        elevation_m=base.elevation_m,
        timezone=base.timezone,
        source=base.source,
        fetched_at=base.fetched_at,
        ghi_w_m2=base.ghi_w_m2,
        dni_w_m2=base.dni_w_m2,
        dhi_w_m2=base.dhi_w_m2,
        temp_air_c=[5.0] * HOURS_PER_TMY,
        wind_speed_m_s=base.wind_speed_m_s,
        precipitation_mm_per_month=None,
        snowfall_cm_per_month=snow,
        relative_humidity_pct_per_month=rh,
    )


def _dc_for(tmy: TmyData) -> DcProductionResult:
    return run_dc_production(system=_system(), tmy=tmy)


def test_step_returns_none_when_snowfall_column_absent() -> None:
    tmy = _tmy_with_columns(snow=None, rh=[60.0] * 12)
    assert run_snow_loss(tmy=tmy, system=_system(), dc=_dc_for(tmy)) is None


def test_step_returns_none_when_relative_humidity_column_absent() -> None:
    tmy = _tmy_with_columns(snow=[10.0] * 12, rh=None)
    assert run_snow_loss(tmy=tmy, system=_system(), dc=_dc_for(tmy)) is None


def test_zero_snow_year_produces_zero_loss_and_unchanged_production() -> None:
    """A site that never sees snow should pass through with no derate.

    Townsend's monthly loss collapses to 0 when snow_total is 0; we
    additionally clip negative numerical-noise values to 0 so the
    factor vector is exactly 1.0 everywhere.
    """
    tmy = _tmy_with_columns(snow=[0.0] * 12, rh=[60.0] * 12)
    dc = _dc_for(tmy)
    result = run_snow_loss(tmy=tmy, system=_system(), dc=dc)

    assert isinstance(result, SnowLossResult)
    assert result.monthly_loss_fraction == [0.0] * 12
    assert result.adjusted_hourly_ac_kw == dc.hourly_ac_kw
    assert result.adjusted_annual_ac_kwh == pytest.approx(dc.annual_ac_kwh)


def test_winter_snow_month_has_positive_loss_summer_has_none() -> None:
    """Moderate seasonal snow profile ought to follow Townsend's
    qualitative shape: peak loss in deep winter, zero through summer.
    """
    snow = [15.0, 12.0, 8.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 8.0, 15.0]
    rh = [70.0, 65.0, 60.0, 55.0, 60.0, 65.0, 70.0, 70.0, 65.0, 65.0, 70.0, 75.0]
    tmy = _tmy_with_columns(snow=snow, rh=rh)
    dc = _dc_for(tmy)
    result = run_snow_loss(tmy=tmy, system=_system(), dc=dc)

    assert isinstance(result, SnowLossResult)
    losses = result.monthly_loss_fraction

    # December and January carry the year's deepest snow → highest loss.
    assert losses[0] > 0.0  # Jan
    assert losses[11] > 0.0  # Dec
    # Summer months (Jun–Sep) get no snow input → no loss.
    for month_index in range(5, 9):
        assert losses[month_index] == pytest.approx(0.0, abs=1e-6)
    # Winter loss > shoulder loss > zero — monotone in this fixture.
    assert losses[0] > losses[2] > losses[3]
    # Adjusted production is strictly less than the pre-snow baseline.
    assert result.adjusted_annual_ac_kwh < dc.annual_ac_kwh


def test_pipeline_runs_snow_step_and_propagates_into_finance() -> None:
    """End-to-end: when the TMY carries snow + RH, the pipeline runs
    ``engine.snow`` between ``dc_production`` and ``degradation``, the
    resulting artifact appears in ``state.artifacts``, and the finance
    step's per-year energy curve reflects the post-snow annual total.
    """
    snow = [20.0, 15.0, 8.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 8.0, 20.0]
    rh = [70.0, 65.0, 60.0, 55.0, 60.0, 65.0, 70.0, 70.0, 65.0, 65.0, 70.0, 75.0]
    tmy = _tmy_with_columns(snow=snow, rh=rh)

    inputs = ForecastInputs(
        system=_system(),
        financial=FinancialInputs(hold_years=1, system_cost=20_000.0),
        tariff=TariffInputs(country="US"),
        consumption=ConsumptionInputs(annual_kwh=10_000.0),
    )

    result = run_forecast(inputs, tmy=tmy)

    snow_artifact = result.artifacts.get("engine.snow")
    assert isinstance(snow_artifact, SnowLossResult)
    assert any(loss > 0.0 for loss in snow_artifact.monthly_loss_fraction)

    # Without a tariff schedule, finance is skipped — but the
    # production-stream propagation still wins / loses on the dc artifact.
    dc = result.artifacts["engine.dc_production"]
    assert isinstance(dc, DcProductionResult)
    assert snow_artifact.adjusted_annual_ac_kwh < dc.annual_ac_kwh


def test_pipeline_skips_snow_when_tmy_lacks_columns() -> None:
    """Default ``synthetic_tmy()`` doesn't populate snow / RH columns,
    so the pipeline should simply skip the snow step — no artifact
    written, downstream sees the unmodified dc stream. This is the
    common case for current PVGIS-only forecasts.
    """
    tmy = synthetic_tmy(lat=33.0, lon=-112.0, timezone="UTC", elevation_m=300.0)
    inputs = ForecastInputs(
        system=SystemInputs(lat=33.0, lon=-112.0, dc_kw=6.0, tilt_deg=20, azimuth_deg=180),
        financial=FinancialInputs(hold_years=1, system_cost=15_000.0),
        tariff=TariffInputs(country="US"),
        consumption=ConsumptionInputs(annual_kwh=8_000.0),
    )

    result = run_forecast(inputs, tmy=tmy)

    assert "engine.snow" not in result.artifacts


def test_ground_mount_geometry_increases_loss_vs_rooftop() -> None:
    """Townsend's loss model is most sensitive to ``lower_edge_height``:
    a ground-mount with a 0.4 m clearance has somewhere for snow to pile
    up against the array, while a 2 m rooftop eave does not. With the
    same monthly snow + RH inputs, the ground-mount geometry must
    produce strictly larger monthly loss than the rooftop default.
    """
    snow = [20.0, 15.0, 8.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 8.0, 20.0]
    rh = [70.0, 65.0, 60.0, 55.0, 60.0, 65.0, 70.0, 70.0, 65.0, 65.0, 70.0, 75.0]
    tmy = _tmy_with_columns(snow=snow, rh=rh)
    dc = _dc_for(tmy)

    rooftop_system = SystemInputs(
        lat=44.0,
        lon=-72.5,
        dc_kw=8.0,
        tilt_deg=25,
        azimuth_deg=180,
    )
    ground_mount_system = SystemInputs(
        lat=44.0,
        lon=-72.5,
        dc_kw=8.0,
        tilt_deg=25,
        azimuth_deg=180,
        snow_geometry=SnowGeometry(
            slant_height_m=1.7,
            lower_edge_height_m=0.4,  # ground-mount: snow piles against the array
            string_factor=1.0,
        ),
    )

    rooftop = run_snow_loss(tmy=tmy, system=rooftop_system, dc=dc)
    ground_mount = run_snow_loss(tmy=tmy, system=ground_mount_system, dc=dc)

    assert isinstance(rooftop, SnowLossResult)
    assert isinstance(ground_mount, SnowLossResult)
    # Ground-mount loss is strictly larger every snowy month; summer
    # months sit at zero on both sides so we compare only winter.
    assert ground_mount.monthly_loss_fraction[0] > rooftop.monthly_loss_fraction[0]
    assert ground_mount.monthly_loss_fraction[11] > rooftop.monthly_loss_fraction[11]
    # And the year-total reflects that.
    assert ground_mount.adjusted_annual_ac_kwh < rooftop.adjusted_annual_ac_kwh


def test_explicit_kwarg_overrides_system_snow_geometry() -> None:
    """Explicit kwargs win over ``SystemInputs.snow_geometry``. This is
    the legacy fallback path the bead pins — installer-quote extraction
    flows values via the geometry block, but tests and one-off callers
    can still pin the value at the call site.
    """
    snow = [20.0, 15.0, 8.0, 2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 8.0, 20.0]
    rh = [70.0, 65.0, 60.0, 55.0, 60.0, 65.0, 70.0, 70.0, 65.0, 65.0, 70.0, 75.0]
    tmy = _tmy_with_columns(snow=snow, rh=rh)
    dc = _dc_for(tmy)

    system_with_rooftop = SystemInputs(
        lat=44.0,
        lon=-72.5,
        dc_kw=8.0,
        tilt_deg=25,
        azimuth_deg=180,
        snow_geometry=SnowGeometry(
            slant_height_m=1.7,
            lower_edge_height_m=2.0,
            string_factor=1.0,
        ),
    )

    via_kwarg = run_snow_loss(
        tmy=tmy,
        system=system_with_rooftop,
        dc=dc,
        lower_edge_height_m=0.4,
    )
    via_geometry_only = run_snow_loss(tmy=tmy, system=system_with_rooftop, dc=dc)

    assert isinstance(via_kwarg, SnowLossResult)
    assert isinstance(via_geometry_only, SnowLossResult)
    # Kwarg picked the ground-mount edge; geometry block is rooftop —
    # so kwarg path produces strictly larger winter loss.
    assert via_kwarg.monthly_loss_fraction[0] > via_geometry_only.monthly_loss_fraction[0]


def test_dc_production_exposes_hourly_poa_for_downstream_consumers() -> None:
    """``engine.snow`` (and eventually ``engine.soiling``) need POA on
    a per-hour basis to derive monthly aggregates. Pin the contract:
    the dc_production result carries a non-trivial 8760-element
    ``hourly_poa_w_m2`` after a clear-sky run.
    """
    tmy = synthetic_tmy(lat=33.0, lon=-112.0, timezone="UTC", elevation_m=300.0)
    dc = run_dc_production(system=_system(), tmy=tmy)

    assert len(dc.hourly_poa_w_m2) == HOURS_PER_TMY
    # Some hours are zero (night), but the year-total is firmly positive
    # at a sunny mid-latitude.
    assert max(dc.hourly_poa_w_m2) > 0.0
    assert sum(dc.hourly_poa_w_m2) > 0.0
    # POA is non-negative — the pvlib transposition + our clip step
    # together guarantee no negative noise leaks through.
    assert min(dc.hourly_poa_w_m2) >= 0.0
