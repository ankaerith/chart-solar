"""Export-credit modeling — NEM 1:1, NEM 3.0/NBT, UK SEG."""

from __future__ import annotations

import pytest

from backend.engine.steps.export_credit import (
    ExportCreditResult,
    apply_nem_one_for_one,
    apply_nem_three_nbt,
    apply_seg_flat,
    apply_seg_tou,
)
from backend.providers.irradiance import HOURS_PER_TMY
from backend.providers.tariff import (
    TariffSchedule,
    TieredBlock,
    TouPeriod,
)


def _flat_tariff(rate: float = 0.30) -> TariffSchedule:
    return TariffSchedule(
        name="flat",
        utility="u",
        country="US",
        currency="USD",
        structure="flat",
        fixed_monthly_charge=0.0,
        flat_rate_per_kwh=rate,
    )


def _tou_tariff() -> TariffSchedule:
    peak = [False] * 24
    for h in range(16, 21):
        peak[h] = True
    off = [not h for h in peak]
    return TariffSchedule(
        name="tou",
        utility="u",
        country="US",
        currency="USD",
        structure="tou",
        fixed_monthly_charge=0.0,
        tou_periods=[
            TouPeriod(
                name="peak",
                rate_per_kwh=0.45,
                months=list(range(1, 13)),
                hour_mask=peak,
                is_weekday=True,
            ),
            TouPeriod(
                name="off",
                rate_per_kwh=0.15,
                months=list(range(1, 13)),
                hour_mask=off,
                is_weekday=True,
            ),
            TouPeriod(
                name="weekend",
                rate_per_kwh=0.18,
                months=list(range(1, 13)),
                hour_mask=[True] * 24,
                is_weekday=False,
            ),
        ],
    )


def _tiered_tariff() -> TariffSchedule:
    return TariffSchedule(
        name="tiered",
        utility="u",
        country="US",
        currency="USD",
        structure="tiered",
        fixed_monthly_charge=0.0,
        tiered_blocks=[
            TieredBlock(rate_per_kwh=0.20, up_to_kwh_per_month=300.0),
            TieredBlock(rate_per_kwh=0.40, up_to_kwh_per_month=None),
        ],
    )


def _zero_export() -> list[float]:
    return [0.0] * HOURS_PER_TMY


def _signed_monthly(*, import_per_month: float, export_per_month: float) -> list[float]:
    """8760-entry signed net load: each month gets ``import_per_month``
    spread across the first chunk of weekday daytime hours (positive)
    and ``export_per_month`` spread across the next chunk (negative).
    Used to construct PG&E-E1-shaped fixtures where the monthly totals
    are easy to reason about — the within-month order doesn't affect
    NEM 1:1 tier-walking netting because we aggregate per month."""
    from backend.providers.irradiance import tmy_hour_calendar

    calendar = tmy_hour_calendar()
    hours_by_month: dict[int, list[int]] = {m: [] for m in range(1, 13)}
    for hour_index, (month, _is_weekday, _hour_of_day) in enumerate(calendar):
        hours_by_month[month].append(hour_index)

    net_load = [0.0] * HOURS_PER_TMY
    for hours in hours_by_month.values():
        # First half of hours: imports; second half: exports. Spread evenly.
        half = len(hours) // 2
        if half == 0:
            continue
        per_import_hour = import_per_month / half
        per_export_hour = export_per_month / (len(hours) - half)
        for hour_index in hours[:half]:
            net_load[hour_index] = per_import_hour
        for hour_index in hours[half:]:
            net_load[hour_index] = -per_export_hour
    return net_load


# ---- NEM 1:1 ---------------------------------------------------------


def test_nem_1to1_flat_credits_at_flat_rate() -> None:
    """1 kWh exported × 8760 hours × $0.30 = $2,628 annual credit."""
    export = [1.0] * HOURS_PER_TMY
    result = apply_nem_one_for_one(hourly_export_kwh=export, tariff=_flat_tariff(0.30))
    assert result.annual_credit == pytest.approx(8760 * 0.30)
    assert result.annual_kwh_exported == pytest.approx(8760.0)
    assert result.regime == "nem_one_for_one"


def test_nem_1to1_tou_uses_band_rate_per_hour() -> None:
    """Single 1 kWh export at Mon 5pm peak vs Mon noon off-peak."""
    # Hour 0 = Sun Jan 1 2023 00:00. Mon Jan 2 5pm = hour 24+17 = 41.
    peak_export = _zero_export()
    peak_export[41] = 1.0
    peak = apply_nem_one_for_one(hourly_export_kwh=peak_export, tariff=_tou_tariff())
    assert peak.annual_credit == pytest.approx(0.45)

    off_export = _zero_export()
    off_export[24 + 12] = 1.0  # Mon Jan 2 noon = off-peak
    off = apply_nem_one_for_one(hourly_export_kwh=off_export, tariff=_tou_tariff())
    assert off.annual_credit == pytest.approx(0.15)


def test_nem_1to1_tiered_requires_signed_net_load() -> None:
    """Tier-walking netting needs imports + exports to derive each
    month's tier-walk delta; passing exports alone can't tell us the
    monthly tier cursor."""
    export = [1.0] * HOURS_PER_TMY
    with pytest.raises(ValueError, match="hourly_net_load_kwh"):
        apply_nem_one_for_one(hourly_export_kwh=export, tariff=_tiered_tariff())


def test_nem_1to1_tiered_nets_export_against_same_month_imports() -> None:
    """PG&E E-1-style fixture: in each month, 500 kWh imported and
    200 kWh exported. The household pays for 300 kWh net at the tier
    walk (cursor 0 → 300 sits entirely in tier 1, $0.20/kWh). Credit
    is the bill delta:
      bill_imports_only(500 kWh) = 300 × 0.20 + 200 × 0.40 = $140
      bill_netted(300 kWh)       = 300 × 0.20             =  $60
      monthly credit             =                           $80
    Annual = 12 × $80 = $960. Surplus exports beyond same-month
    imports forfeit (none here — exports < imports every month)."""
    net_load = _signed_monthly(import_per_month=500.0, export_per_month=200.0)
    export = [max(0.0, -nl) for nl in net_load]
    result = apply_nem_one_for_one(
        hourly_export_kwh=export,
        tariff=_tiered_tariff(),
        hourly_net_load_kwh=net_load,
    )
    assert result.regime == "nem_one_for_one"
    assert result.annual_credit == pytest.approx(12 * 80.0)
    for monthly in result.monthly_credit:
        assert monthly == pytest.approx(80.0)


def test_nem_1to1_tiered_pure_net_exporter_month_credits_full_import_bill() -> None:
    """Net exporter month: 100 kWh imported, 800 kWh exported. Netted
    monthly billable = 0; credit = full imports-only bill = 100 × $0.20
    = $20. The remaining 700 kWh export forfeits — this helper doesn't
    bank surplus across months."""
    net_load = _signed_monthly(import_per_month=100.0, export_per_month=800.0)
    export = [max(0.0, -nl) for nl in net_load]
    result = apply_nem_one_for_one(
        hourly_export_kwh=export,
        tariff=_tiered_tariff(),
        hourly_net_load_kwh=net_load,
    )
    assert result.annual_credit == pytest.approx(12 * 20.0)
    # Only the 100 kWh that offset same-month imports is "credited"
    # — the 700 kWh of forfeit surplus drops out of annual_kwh_exported.
    assert result.annual_kwh_exported == pytest.approx(12 * 100.0)


def test_nem_1to1_tiered_credit_is_strictly_below_top_rate_upper_bound() -> None:
    """Regression check vs the previous conservative-upper-bound model.
    A net-importer household with modest exports must see less credit
    than (export_kwh × top_tier_rate) — that's the whole point of
    chart-solar-f7n7."""
    # 200 kWh imports, 50 kWh exports per month: net importer, exports
    # offset only the top-tier portion of the imports-only bill (which
    # in this case is 0 because 200 < tier-1 cap of 300). So actual
    # credit is much smaller than 50 × $0.40.
    net_load = _signed_monthly(import_per_month=200.0, export_per_month=50.0)
    export = [max(0.0, -nl) for nl in net_load]
    result = apply_nem_one_for_one(
        hourly_export_kwh=export,
        tariff=_tiered_tariff(),
        hourly_net_load_kwh=net_load,
    )
    # bill_imports(200) = 200 × 0.20 = 40
    # bill_netted(150)  = 150 × 0.20 = 30
    # monthly credit    = 10  (vs naive 50 × 0.40 = 20)
    assert result.annual_credit == pytest.approx(12 * 10.0)
    assert result.annual_credit < 12 * 50 * 0.40


def test_nem_1to1_negative_export_clamped_to_zero() -> None:
    """Defensive — caller passing signed net load shouldn't yield
    negative credit on import hours."""
    export = [-1.0] * HOURS_PER_TMY
    result = apply_nem_one_for_one(hourly_export_kwh=export, tariff=_flat_tariff(0.30))
    assert result.annual_credit == pytest.approx(0.0)
    assert result.annual_kwh_exported == pytest.approx(0.0)


def test_nem_1to1_tou_with_unmatched_hour_raises() -> None:
    """Coverage gap in TOU tariff → raises so the bug isn't silent."""
    peak = [False] * 24
    for h in range(16, 21):
        peak[h] = True
    incomplete = TariffSchedule(
        name="weekday only",
        utility="u",
        country="US",
        currency="USD",
        structure="tou",
        fixed_monthly_charge=0.0,
        tou_periods=[
            TouPeriod(
                name="peak",
                rate_per_kwh=0.45,
                months=list(range(1, 13)),
                hour_mask=peak,
                is_weekday=True,
            ),
        ],
    )
    export = _zero_export()
    export[0] = 1.0  # Sunday — not covered by weekday-only tariff
    with pytest.raises(ValueError, match="NEM 1:1 needs a TOU rate"):
        apply_nem_one_for_one(hourly_export_kwh=export, tariff=incomplete)


# ---- NEM 3.0 / NBT --------------------------------------------------


def test_nbt_credits_at_acc_vector_rate() -> None:
    """1 kWh exported every hour × $0.05/kWh ACC = $438/yr."""
    export = [1.0] * HOURS_PER_TMY
    acc = [0.05] * HOURS_PER_TMY
    result = apply_nem_three_nbt(
        hourly_export_kwh=export,
        hourly_avoided_cost_per_kwh=acc,
    )
    assert result.annual_credit == pytest.approx(8760 * 0.05)
    assert result.regime == "nem_three_nbt"


def test_nbt_negative_acc_during_midday_glut_reduces_credit() -> None:
    """CPUC ACC occasionally dips negative during spring-glut hours;
    homeowner pays for export in those hours under NBT.

    Result preserves the signed total — the caller decides whether
    to floor at zero before rendering a "$" number."""
    export = [1.0] * HOURS_PER_TMY
    acc = [0.0] * HOURS_PER_TMY
    acc[100] = -0.01
    acc[200] = -0.01
    result = apply_nem_three_nbt(
        hourly_export_kwh=export,
        hourly_avoided_cost_per_kwh=acc,
    )
    assert result.monthly_credit[0] == pytest.approx(-0.02, abs=1e-9)
    assert result.annual_credit == pytest.approx(-0.02, abs=1e-9)


def test_nbt_misaligned_inputs_rejected() -> None:
    with pytest.raises(ValueError, match="must be 8760"):
        apply_nem_three_nbt(
            hourly_export_kwh=[1.0] * 100,
            hourly_avoided_cost_per_kwh=[0.05] * 100,
        )


def test_nbt_low_credit_vs_retail_resi_payback_intuition() -> None:
    """NEM 1:1 credits at retail (~$0.40/kWh in CA), NBT at avoided
    cost (~$0.05/kWh average). On the same export profile, NBT is
    ~8× lower — that's the headline NEM 3.0 impact."""
    export = [1.0] * HOURS_PER_TMY
    nem_one = apply_nem_one_for_one(
        hourly_export_kwh=export,
        tariff=_flat_tariff(0.40),
    )
    nbt = apply_nem_three_nbt(
        hourly_export_kwh=export,
        hourly_avoided_cost_per_kwh=[0.05] * HOURS_PER_TMY,
    )
    assert nem_one.annual_credit > nbt.annual_credit * 5


# ---- UK SEG flat -----------------------------------------------------


def test_seg_flat_credits_at_supplier_rate() -> None:
    """Octopus Outgoing flat at 15p/kWh on 1000 kWh export = £150."""
    export = _zero_export()
    for h in range(1000):
        export[h] = 1.0
    result = apply_seg_flat(hourly_export_kwh=export, rate_per_kwh=0.15)
    assert result.annual_credit == pytest.approx(150.0)
    assert result.annual_kwh_exported == pytest.approx(1000.0)
    assert result.regime == "seg_flat"


def test_seg_flat_zero_rate_yields_zero_credit() -> None:
    """E.ON Next Export sat at 0p/kWh in 2024 — pin that the math
    handles a zero-rate SEG without dividing by zero etc."""
    result = apply_seg_flat(
        hourly_export_kwh=[1.0] * HOURS_PER_TMY,
        rate_per_kwh=0.0,
    )
    assert result.annual_credit == pytest.approx(0.0)


def test_seg_flat_rejects_negative_rate() -> None:
    with pytest.raises(ValueError, match="rate_per_kwh must be >= 0"):
        apply_seg_flat(hourly_export_kwh=[1.0] * HOURS_PER_TMY, rate_per_kwh=-0.01)


# ---- UK SEG TOU (Octopus Agile-style) -------------------------------


def test_seg_tou_credits_per_hour_at_vector_rate() -> None:
    rate_vector = [0.10] * HOURS_PER_TMY
    rate_vector[0] = 0.30  # Surge hour
    export = _zero_export()
    export[0] = 2.0
    export[1] = 1.0
    result = apply_seg_tou(
        hourly_export_kwh=export,
        hourly_rate_per_kwh=rate_vector,
    )
    expected = 2.0 * 0.30 + 1.0 * 0.10
    assert result.annual_credit == pytest.approx(expected)
    assert result.regime == "seg_tou"


# ---- common --------------------------------------------------------


def test_export_credit_result_round_trips_through_json() -> None:
    result = apply_seg_flat(
        hourly_export_kwh=[1.0] * HOURS_PER_TMY,
        rate_per_kwh=0.15,
    )
    payload = result.model_dump(mode="json")
    revived = ExportCreditResult.model_validate(payload)
    assert revived.annual_credit == pytest.approx(result.annual_credit)
    assert revived.regime == result.regime
    assert len(revived.monthly_credit) == 12
