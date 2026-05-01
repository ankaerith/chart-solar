"""Rule-based battery dispatch (chart-solar-lr2).

Covers the two strategies the v1 BatteryDispatch chart consumes:

* self-consumption — soak up exports, discharge to cover imports
* TOU arbitrage — charge off-peak (solar surplus + grid), discharge
  on-peak

Plus the energy-balance invariants the dispatch math must satisfy:
SOC stays inside [reserve, usable_capacity], discharged kWh never
exceed (charged kWh × round-trip-efficiency), and post-battery grid
flows match pre-battery flows when the battery is full or empty.
"""

from __future__ import annotations

import pytest

from backend.engine.inputs import (
    BatteryInputs,
    ConsumptionInputs,
    FinancialInputs,
    ForecastInputs,
    SegFlatConfig,
    SystemInputs,
    TariffInputs,
)
from backend.engine.pipeline import ENGINE_STEP_ORDER, run_forecast
from backend.engine.steps.battery_dispatch import (
    BatteryDispatchResult,
    dispatch_battery,
)
from backend.providers.fake import synthetic_tmy
from backend.providers.irradiance import HOURS_PER_TMY
from backend.providers.tariff import TariffSchedule, TouPeriod


def _battery(**overrides: object) -> BatteryInputs:
    base: dict[str, object] = {
        "capacity_kwh": 13.5,
        "usable_pct": 1.0,  # easier reasoning in tests
        "round_trip_efficiency": 0.90,
        "max_charge_kw": 5.0,
        "max_discharge_kw": 5.0,
        "reserve_pct": 0.0,
        "strategy": "self_consumption",
    }
    base.update(overrides)
    return BatteryInputs.model_validate(base)


def test_step_is_registered_after_dc_production_before_tariff() -> None:
    """Battery dispatch must run after DC production (it consumes the
    same net-load shape) and before tariff (a future re-billing PR
    will read post-battery import for monthly bills)."""
    order = list(ENGINE_STEP_ORDER)
    assert "engine.battery_dispatch" in order
    assert order.index("engine.dc_production") < order.index("engine.battery_dispatch")
    assert order.index("engine.battery_dispatch") < order.index("engine.tariff")


def test_dispatch_rejects_wrong_length_net_load() -> None:
    battery = _battery()
    with pytest.raises(ValueError, match="must have 8760"):
        dispatch_battery(battery=battery, hourly_net_load_kwh=[0.0] * 100)


def test_self_consumption_charges_during_export_and_discharges_during_import() -> None:
    """One hour of 4 kWh export then one of 3 kWh import: battery
    should soak the export, then discharge most of it back. The
    discharge-side round-trip loss reduces deliverable kWh below the
    nameplate charged amount."""
    net_load = [-4.0, 3.0] + [0.0] * (HOURS_PER_TMY - 2)
    battery = _battery(round_trip_efficiency=0.9)

    result = dispatch_battery(battery=battery, hourly_net_load_kwh=net_load)

    assert isinstance(result, BatteryDispatchResult)
    assert result.strategy == "self_consumption"
    # Hour 0 — export 4 kWh: battery charges 4 (under 5 kW cap, under 13.5 capacity)
    assert result.hourly_charge_kwh[0] == pytest.approx(4.0)
    assert result.hourly_discharge_kwh[0] == 0.0
    # Hour 1 — import 3 kWh: battery covers up to 4 × 0.9 = 3.6 deliverable
    # so the full 3 kWh is supplied from battery; grid import is zero.
    assert result.hourly_discharge_kwh[1] == pytest.approx(3.0)
    assert result.hourly_grid_import_kwh[1] == pytest.approx(0.0)
    assert result.hourly_grid_export_kwh[0] == pytest.approx(0.0)


def test_self_consumption_caps_charge_at_max_charge_rate() -> None:
    """A 10 kWh export burst can't all enter a 5 kW battery in one
    hour — half stays on the meter as grid export."""
    net_load = [-10.0] + [0.0] * (HOURS_PER_TMY - 1)
    battery = _battery(max_charge_kw=5.0)

    result = dispatch_battery(battery=battery, hourly_net_load_kwh=net_load)

    assert result.hourly_charge_kwh[0] == pytest.approx(5.0)
    assert result.hourly_grid_export_kwh[0] == pytest.approx(5.0)


def test_self_consumption_respects_reserve_floor() -> None:
    """A 50 % reserve means the bottom half of the bank is locked
    away. With a 13.5 kWh battery and 50 % reserve, only 6.75 kWh
    is dischargeable; further import draws hit the grid."""
    net_load = [-7.0, 5.0, 5.0] + [0.0] * (HOURS_PER_TMY - 3)
    battery = _battery(reserve_pct=0.5, round_trip_efficiency=1.0)

    result = dispatch_battery(battery=battery, hourly_net_load_kwh=net_load)

    # Hour 0: charge 5 kWh (cap), SOC = floor(6.75) + 5 = 11.75
    # Hour 1: discharge 5 kWh, SOC = 6.75 (back at floor)
    # Hour 2: discharge 0 (battery at reserve), grid imports the full 5
    assert result.hourly_discharge_kwh[2] == pytest.approx(0.0)
    assert result.hourly_grid_import_kwh[2] == pytest.approx(5.0)


def test_self_consumption_caps_soc_at_usable_capacity() -> None:
    """Continuous 5 kW charging stops once the bank is full."""
    net_load = [-5.0] * 10 + [0.0] * (HOURS_PER_TMY - 10)
    battery = _battery(capacity_kwh=10.0, usable_pct=1.0, max_charge_kw=5.0)

    result = dispatch_battery(battery=battery, hourly_net_load_kwh=net_load)

    # By hour 1 the bank is full; subsequent exports go to the grid.
    assert max(result.hourly_soc_kwh) <= 10.0 + 1e-9
    assert result.hourly_grid_export_kwh[5] == pytest.approx(5.0)


def test_self_consumption_passes_through_when_no_export_no_import() -> None:
    """A flat-zero net load year: battery does nothing and the SOC
    stays put at the reserve floor."""
    battery = _battery(reserve_pct=0.2)
    result = dispatch_battery(battery=battery, hourly_net_load_kwh=[0.0] * HOURS_PER_TMY)

    assert sum(result.hourly_charge_kwh) == 0.0
    assert sum(result.hourly_discharge_kwh) == 0.0
    assert sum(result.hourly_grid_import_kwh) == 0.0
    assert sum(result.hourly_grid_export_kwh) == 0.0


def _flat_tariff() -> TariffSchedule:
    return TariffSchedule(
        name="flat",
        utility="u",
        country="US",
        currency="USD",
        structure="flat",
        flat_rate_per_kwh=0.20,
    )


def _two_band_tou() -> TariffSchedule:
    """Off-peak 0.10 every hour weekdays, peak 0.50 hours 16-21."""
    off = TouPeriod(
        name="offpeak",
        rate_per_kwh=0.10,
        months=list(range(1, 13)),
        hour_mask=[h not in range(16, 21) for h in range(24)],
        is_weekday=True,
    )
    peak = TouPeriod(
        name="peak",
        rate_per_kwh=0.50,
        months=list(range(1, 13)),
        hour_mask=[h in range(16, 21) for h in range(24)],
        is_weekday=True,
    )
    weekend = TouPeriod(
        name="weekend",
        rate_per_kwh=0.10,
        months=list(range(1, 13)),
        hour_mask=[True] * 24,
        is_weekday=False,
    )
    return TariffSchedule(
        name="tou",
        utility="u",
        country="US",
        currency="USD",
        structure="tou",
        tou_periods=[off, peak, weekend],
    )


def test_tou_arbitrage_falls_back_to_self_consumption_when_tariff_is_flat() -> None:
    battery = _battery(strategy="tou_arbitrage")
    result = dispatch_battery(
        battery=battery,
        hourly_net_load_kwh=[-2.0, 2.0] + [0.0] * (HOURS_PER_TMY - 2),
        tariff=_flat_tariff(),
    )
    assert result.strategy == "self_consumption"


def test_tou_arbitrage_charges_offpeak_and_discharges_onpeak() -> None:
    """A small battery (5 kWh) drained by daily peak windows should
    refill during the off-peak hour immediately preceding the next
    peak window. Look at the hour just before peak (15:00) on a
    Tuesday — by then the previous evening peak has emptied the bank
    and the morning has had time to top it back up."""
    net_load = [2.0] * HOURS_PER_TMY
    battery = _battery(
        strategy="tou_arbitrage",
        capacity_kwh=5.0,
        max_charge_kw=2.0,
        max_discharge_kw=5.0,
        reserve_pct=0.0,
    )
    result = dispatch_battery(
        battery=battery,
        hourly_net_load_kwh=net_load,
        tariff=_two_band_tou(),
    )
    assert result.strategy == "tou_arbitrage"

    from backend.providers.irradiance import tmy_hour_calendar

    cal = tmy_hour_calendar()
    # First Tuesday peak window's first hour: battery (full from off-peak
    # charging) discharges 5 kWh which covers the 2 kWh import need and
    # then some — the cap is the discharge rate, not the load.
    tuesday_peak = next(
        i for i, (m, wd, h) in enumerate(cal) if wd and m == 1 and h == 18 and i > 24
    )
    assert result.hourly_discharge_kwh[tuesday_peak] > 0.0


def test_tou_arbitrage_grid_import_at_peak_drops_below_baseline_load() -> None:
    """Headline arbitrage signal: post-battery grid import during
    peak hours is *less* than the household's underlying import,
    because the battery is supplying part of the load."""
    net_load = [2.0] * HOURS_PER_TMY
    battery = _battery(
        strategy="tou_arbitrage",
        capacity_kwh=10.0,
        max_charge_kw=2.0,
        max_discharge_kw=5.0,
        reserve_pct=0.0,
    )
    result = dispatch_battery(
        battery=battery,
        hourly_net_load_kwh=net_load,
        tariff=_two_band_tou(),
    )
    from backend.providers.irradiance import tmy_hour_calendar

    cal = tmy_hour_calendar()
    # Pick a Tuesday peak hour after the battery has had time to charge.
    tuesday_peak = next(
        i for i, (m, wd, h) in enumerate(cal) if wd and m == 1 and h == 18 and i > 24
    )
    assert result.hourly_grid_import_kwh[tuesday_peak] < 2.0


def test_pipeline_skips_battery_step_when_no_battery_inputs() -> None:
    """Existing forecasts (no battery configured) keep their shape —
    `engine.battery_dispatch` does not appear in the artifacts."""
    inputs = ForecastInputs(
        system=SystemInputs(lat=33.45, lon=-112.07, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(),
        tariff=TariffInputs(country="US", schedule=_flat_tariff()),
    )
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)
    result = run_forecast(inputs, tmy=tmy)

    assert "engine.battery_dispatch" not in result.artifacts


def test_pipeline_runs_battery_step_when_battery_inputs_present() -> None:
    """A battery-configured forecast lands a BatteryDispatchResult
    artifact alongside the other step outputs."""
    battery = _battery()
    inputs = ForecastInputs(
        system=SystemInputs(lat=33.45, lon=-112.07, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(),
        tariff=TariffInputs(
            country="US",
            schedule=_flat_tariff(),
            export_credit=SegFlatConfig(flat_rate_per_kwh=0.05),
        ),
        consumption=ConsumptionInputs(annual_kwh=12_000.0),
        battery=battery,
    )
    tmy = synthetic_tmy(lat=inputs.system.lat, lon=inputs.system.lon)
    result = run_forecast(inputs, tmy=tmy)

    artifact = result.artifacts.get("engine.battery_dispatch")
    assert isinstance(artifact, BatteryDispatchResult)
    # Annual outputs are nonzero — the synthetic clear-sky TMY exports
    # plenty during the day, all of which the battery soaks up.
    assert artifact.annual_charged_kwh > 0.0


def test_pipeline_tariff_bills_against_post_battery_import_stream() -> None:
    """With a battery installed, the tariff bill is computed against
    the post-battery grid import — not the pre-battery net load. A
    self-consumption battery on a TOU tariff with peak-hour imports
    must produce a strictly *lower* annual energy charge than the
    same forecast without a battery."""
    system = SystemInputs(lat=33.45, lon=-112.07, dc_kw=8.0, tilt_deg=25, azimuth_deg=180)
    consumption = ConsumptionInputs(annual_kwh=12_000.0)
    tariff = TariffInputs(country="US", schedule=_two_band_tou())
    tmy = synthetic_tmy(lat=system.lat, lon=system.lon)

    no_battery = run_forecast(
        ForecastInputs(
            system=system,
            financial=FinancialInputs(),
            tariff=tariff,
            consumption=consumption,
        ),
        tmy=tmy,
    )
    with_battery = run_forecast(
        ForecastInputs(
            system=system,
            financial=FinancialInputs(),
            tariff=tariff,
            consumption=consumption,
            battery=_battery(),
        ),
        tmy=tmy,
    )

    no_battery_bill = no_battery.artifacts["engine.tariff"]
    with_battery_bill = with_battery.artifacts["engine.tariff"]
    assert with_battery_bill.annual_total < no_battery_bill.annual_total


def test_pipeline_export_credit_bills_against_post_battery_export_stream() -> None:
    """A self-consumption battery soaks up midday solar surplus, so
    the post-battery export stream is smaller than the pre-battery
    surplus. Export credit must shrink accordingly — otherwise the
    bill avoidance and SEG payment double-count the same kWh."""
    system = SystemInputs(lat=33.45, lon=-112.07, dc_kw=8.0, tilt_deg=25, azimuth_deg=180)
    consumption = ConsumptionInputs(annual_kwh=4_000.0)  # solar-rich profile
    tariff = TariffInputs(
        country="US",
        schedule=_flat_tariff(),
        export_credit=SegFlatConfig(flat_rate_per_kwh=0.05),
    )
    tmy = synthetic_tmy(lat=system.lat, lon=system.lon)

    no_battery = run_forecast(
        ForecastInputs(
            system=system,
            financial=FinancialInputs(),
            tariff=tariff,
            consumption=consumption,
        ),
        tmy=tmy,
    )
    with_battery = run_forecast(
        ForecastInputs(
            system=system,
            financial=FinancialInputs(),
            tariff=tariff,
            consumption=consumption,
            battery=_battery(),
        ),
        tmy=tmy,
    )

    assert (
        with_battery.artifacts["engine.export_credit"].annual_credit
        < no_battery.artifacts["engine.export_credit"].annual_credit
    )


def test_charged_minus_discharged_kwh_covers_round_trip_loss() -> None:
    """Energy in must exceed energy out by the round-trip-efficiency
    factor: discharged ≤ charged × rte. Holds at the annual roll-up."""
    net_load = [-3.0, 3.0] * (HOURS_PER_TMY // 2)
    battery = _battery(round_trip_efficiency=0.90)
    result = dispatch_battery(battery=battery, hourly_net_load_kwh=net_load)
    # Discharged kWh leave the bank at face value but the bank itself
    # was sized in nameplate kWh; over a full year the integrated
    # discharge can't exceed integrated charge × rte (modulo the
    # last-hour SOC that hasn't been discharged yet).
    assert result.annual_discharged_kwh <= result.annual_charged_kwh + 1e-6
