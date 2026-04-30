"""Tariff billing — flat / tiered / TOU."""

from __future__ import annotations

import pytest

from backend.engine.steps.tariff import (
    AnnualBill,
    compute_annual_bill,
)
from backend.providers.irradiance import HOURS_PER_TMY
from backend.providers.tariff import (
    TariffSchedule,
    TieredBlock,
    TouPeriod,
)


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


def _tiered_tariff() -> TariffSchedule:
    """PG&E-style tiered: 0-300 kWh @ 0.20, 300-600 @ 0.30, 600+ @ 0.40."""
    return TariffSchedule(
        name="test tiered",
        utility="test-util",
        country="US",
        currency="USD",
        structure="tiered",
        fixed_monthly_charge=10.0,
        tiered_blocks=[
            TieredBlock(rate_per_kwh=0.20, up_to_kwh_per_month=300.0),
            TieredBlock(rate_per_kwh=0.30, up_to_kwh_per_month=600.0),
            TieredBlock(rate_per_kwh=0.40, up_to_kwh_per_month=None),
        ],
    )


def _tou_tariff() -> TariffSchedule:
    """Simple two-period TOU: peak weekdays 4-9pm, off-peak everything else."""
    peak_mask = [False] * 24
    for hour in range(16, 21):  # 16, 17, 18, 19, 20 = 4pm-9pm
        peak_mask[hour] = True
    off_peak_mask = [not h for h in peak_mask]

    return TariffSchedule(
        name="test tou",
        utility="test-util",
        country="US",
        currency="USD",
        structure="tou",
        fixed_monthly_charge=10.0,
        tou_periods=[
            TouPeriod(
                name="peak weekday",
                rate_per_kwh=0.45,
                months=list(range(1, 13)),
                hour_mask=peak_mask,
                is_weekday=True,
            ),
            TouPeriod(
                name="off-peak weekday",
                rate_per_kwh=0.15,
                months=list(range(1, 13)),
                hour_mask=off_peak_mask,
                is_weekday=True,
            ),
            TouPeriod(
                name="weekend all-day",
                rate_per_kwh=0.18,
                months=list(range(1, 13)),
                hour_mask=[True] * 24,
                is_weekday=False,
            ),
        ],
    )


def _flat_load(kwh_per_hour: float) -> list[float]:
    return [kwh_per_hour] * HOURS_PER_TMY


def test_flat_tariff_bill_matches_handcomputed() -> None:
    """1 kWh/h × 8760 hours × $0.16 = $1,401.60 energy + $120 fixed."""
    bill = compute_annual_bill(
        hourly_net_load_kwh=_flat_load(1.0),
        tariff=_flat_tariff(rate=0.16, fixed=10.0),
    )
    assert bill.annual_energy_charge == pytest.approx(8760 * 0.16, rel=1e-9)
    assert bill.annual_fixed_charge == pytest.approx(120.0)
    assert bill.annual_kwh_imported == pytest.approx(8760.0)
    assert bill.annual_total == pytest.approx(8760 * 0.16 + 120.0)


def test_flat_tariff_bill_per_month_proportional_to_hours() -> None:
    """31-day months bill more than 28-day Feb."""
    bill = compute_annual_bill(
        hourly_net_load_kwh=_flat_load(1.0),
        tariff=_flat_tariff(rate=0.20, fixed=0.0),
    )
    jan = next(m for m in bill.monthly if m.month == 1)
    feb = next(m for m in bill.monthly if m.month == 2)
    assert jan.energy_charge > feb.energy_charge
    # Jan has 744 hours, Feb has 672
    assert jan.kwh_imported == pytest.approx(744.0)
    assert feb.kwh_imported == pytest.approx(672.0)


def test_flat_tariff_negative_net_load_treated_as_zero_import() -> None:
    """Solar overproducing → negative net load → no energy charge,
    but still pay the fixed monthly."""
    bill = compute_annual_bill(
        hourly_net_load_kwh=[-1.0] * HOURS_PER_TMY,
        tariff=_flat_tariff(rate=0.16, fixed=10.0),
    )
    assert bill.annual_energy_charge == pytest.approx(0.0)
    assert bill.annual_fixed_charge == pytest.approx(120.0)
    assert bill.annual_total == pytest.approx(120.0)


def test_tiered_tariff_under_first_threshold_bills_at_first_rate() -> None:
    """200 kWh in January (well under 300 threshold) → all at $0.20.
    Use 200 hours at 1 kWh/h, all comfortably inside Jan's 744 hours."""
    hourly = [0.0] * HOURS_PER_TMY
    for h in range(200):
        hourly[h] = 1.0
    bill = compute_annual_bill(hourly_net_load_kwh=hourly, tariff=_tiered_tariff())
    jan = next(m for m in bill.monthly if m.month == 1)
    assert jan.kwh_imported == pytest.approx(200.0)
    assert jan.energy_charge == pytest.approx(200.0 * 0.20)


def test_tiered_tariff_crosses_threshold_within_month() -> None:
    """450 kWh in Jan: first 300 @ $0.20 = $60, next 150 @ $0.30 = $45.
    450 hours of 1.0 fits inside Jan's 744 hours."""
    hourly = [0.0] * HOURS_PER_TMY
    for h in range(450):
        hourly[h] = 1.0
    bill = compute_annual_bill(hourly_net_load_kwh=hourly, tariff=_tiered_tariff())
    jan = next(m for m in bill.monthly if m.month == 1)
    expected = 300 * 0.20 + 150 * 0.30
    assert jan.energy_charge == pytest.approx(expected)


def test_tiered_tariff_uses_top_block_above_all_thresholds() -> None:
    """800 kWh in Jan: 300 @ $0.20 + 300 @ $0.30 + 200 @ $0.40 = $230.
    Use 400 hours at 2.0 kWh/h to fit 800 kWh inside January."""
    hourly = [0.0] * HOURS_PER_TMY
    for h in range(400):
        hourly[h] = 2.0
    bill = compute_annual_bill(hourly_net_load_kwh=hourly, tariff=_tiered_tariff())
    jan = next(m for m in bill.monthly if m.month == 1)
    expected = 300 * 0.20 + 300 * 0.30 + 200 * 0.40
    assert jan.energy_charge == pytest.approx(expected)


def test_tiered_tariff_resets_monthly_counter() -> None:
    """200 kWh in Jan and 200 kWh in Feb both bill at the first tier
    (each month resets the cumulative counter)."""
    hourly = [0.0] * HOURS_PER_TMY
    # Jan: hours 0..199 at 1 kWh
    for h in range(200):
        hourly[h] = 1.0
    # February starts at hour 744.
    for h in range(744, 944):
        hourly[h] = 1.0
    bill = compute_annual_bill(hourly_net_load_kwh=hourly, tariff=_tiered_tariff())
    jan = next(m for m in bill.monthly if m.month == 1)
    feb = next(m for m in bill.monthly if m.month == 2)
    assert jan.energy_charge == pytest.approx(200 * 0.20)
    assert feb.energy_charge == pytest.approx(200 * 0.20)


def test_tou_tariff_peak_hour_charges_higher() -> None:
    """1 kWh import at noon weekday (off-peak) vs 5pm weekday (peak)."""
    hourly = [0.0] * HOURS_PER_TMY
    # Hour 0 = Sun Jan 1 2023 00:00 UTC
    # Mon Jan 2 2023, weekday hour 17 (5pm) = hour index 24+17 = 41
    hourly[41] = 1.0
    peak_only = compute_annual_bill(hourly_net_load_kwh=hourly, tariff=_tou_tariff())
    assert peak_only.annual_energy_charge == pytest.approx(0.45)

    hourly = [0.0] * HOURS_PER_TMY
    hourly[24 + 12] = 1.0  # Mon noon = off-peak weekday
    off_peak = compute_annual_bill(hourly_net_load_kwh=hourly, tariff=_tou_tariff())
    assert off_peak.annual_energy_charge == pytest.approx(0.15)


def test_tou_tariff_weekend_uses_weekend_band() -> None:
    """Hour 0 = Sun Jan 1 2023 → weekend band at $0.18."""
    hourly = [0.0] * HOURS_PER_TMY
    hourly[0] = 1.0
    bill = compute_annual_bill(hourly_net_load_kwh=hourly, tariff=_tou_tariff())
    assert bill.annual_energy_charge == pytest.approx(0.18)


def test_tou_tariff_unmatched_hour_raises() -> None:
    """A tariff with a gap in coverage must surface the bug, not
    silently bill at zero."""
    incomplete = TariffSchedule(
        name="incomplete tou",
        utility="test-util",
        country="US",
        currency="USD",
        structure="tou",
        fixed_monthly_charge=0.0,
        tou_periods=[
            TouPeriod(
                name="weekend only",
                rate_per_kwh=0.20,
                months=list(range(1, 13)),
                hour_mask=[True] * 24,
                is_weekday=False,
            ),
        ],
    )
    hourly = [0.0] * HOURS_PER_TMY
    hourly[24 + 12] = 1.0  # Monday noon — no matching band
    with pytest.raises(ValueError, match="no TOU period matches"):
        compute_annual_bill(hourly_net_load_kwh=hourly, tariff=incomplete)


def test_fixed_charge_applies_every_month_even_at_zero_load() -> None:
    bill = compute_annual_bill(
        hourly_net_load_kwh=[0.0] * HOURS_PER_TMY,
        tariff=_flat_tariff(rate=0.16, fixed=10.0),
    )
    assert bill.annual_energy_charge == pytest.approx(0.0)
    assert bill.annual_fixed_charge == pytest.approx(120.0)
    for month_bill in bill.monthly:
        assert month_bill.fixed_charge == pytest.approx(10.0)
        assert month_bill.energy_charge == pytest.approx(0.0)


def test_misaligned_hourly_load_rejected() -> None:
    with pytest.raises(ValueError, match="must be 8760"):
        compute_annual_bill(
            hourly_net_load_kwh=[1.0] * 100,
            tariff=_flat_tariff(),
        )


def test_annual_total_equals_sum_of_monthly_totals() -> None:
    bill = compute_annual_bill(
        hourly_net_load_kwh=_flat_load(1.5),
        tariff=_tiered_tariff(),
    )
    assert bill.annual_total == pytest.approx(sum(m.total for m in bill.monthly))


def test_annual_kwh_equals_sum_of_monthly_kwh() -> None:
    bill = compute_annual_bill(
        hourly_net_load_kwh=_flat_load(2.0),
        tariff=_flat_tariff(),
    )
    assert bill.annual_kwh_imported == pytest.approx(sum(m.kwh_imported for m in bill.monthly))


def test_bill_round_trips_through_json() -> None:
    bill = compute_annual_bill(
        hourly_net_load_kwh=_flat_load(1.0),
        tariff=_flat_tariff(),
    )
    payload = bill.model_dump(mode="json")
    revived = AnnualBill.model_validate(payload)
    assert revived.annual_total == pytest.approx(bill.annual_total)
    assert revived.currency == bill.currency
    assert len(revived.monthly) == 12
