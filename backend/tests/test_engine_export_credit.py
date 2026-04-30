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


def test_nem_1to1_tiered_credits_at_top_rate() -> None:
    """Tiered NEM 1:1 credits at the top tier rate as the conservative
    "marginal value of avoiding an import" upper bound."""
    export = [1.0] * HOURS_PER_TMY
    result = apply_nem_one_for_one(hourly_export_kwh=export, tariff=_tiered_tariff())
    assert result.annual_credit == pytest.approx(8760 * 0.40)


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
