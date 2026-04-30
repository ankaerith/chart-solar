"""NBT monthly true-up netting (chart-solar-ri57).

Pins the integration semantics between the standalone tariff bill
(``engine.tariff``) and the NBT export credit (``engine.export_credit``):
within-month netting, surplus roll-forward, in-month settlement of
negative-credit hours, year-end zero-out.
"""

from __future__ import annotations

import pytest

from backend.engine.integration.nbt import (
    NbtSettlement,
    compute_nbt_net_bill,
)
from backend.engine.steps.export_credit import ExportCreditResult
from backend.engine.steps.tariff import AnnualBill, MonthlyBill


def _bill(monthly_charges: list[float], fixed: float = 10.0) -> AnnualBill:
    """Build an AnnualBill from twelve monthly energy charges."""
    if len(monthly_charges) != 12:
        raise AssertionError("provide 12 monthly charges")
    monthly = [
        MonthlyBill(
            month=i + 1,
            kwh_imported=charge / 0.30 if charge > 0 else 0.0,
            energy_charge=charge,
            fixed_charge=fixed,
            total=charge + fixed,
        )
        for i, charge in enumerate(monthly_charges)
    ]
    return AnnualBill(
        currency="USD",
        monthly=monthly,
        annual_kwh_imported=sum(m.kwh_imported for m in monthly),
        annual_energy_charge=sum(monthly_charges),
        annual_fixed_charge=fixed * 12,
        annual_total=sum(m.total for m in monthly),
    )


def _credit(monthly_credits: list[float]) -> ExportCreditResult:
    if len(monthly_credits) != 12:
        raise AssertionError("provide 12 monthly credits")
    return ExportCreditResult(
        regime="nem_three_nbt",
        monthly_credit=monthly_credits,
        annual_credit=sum(monthly_credits),
        annual_kwh_exported=1000.0,  # arbitrary; not consumed by the netter
    )


def test_within_month_netting_reduces_energy_charge() -> None:
    """Single-month case: $30 credit applied to a $100 charge → $70 net."""
    bill = _bill([100.0] + [0.0] * 11)
    credit = _credit([30.0] + [0.0] * 11)
    result = compute_nbt_net_bill(annual_bill=bill, export_credit=credit)

    assert isinstance(result, NbtSettlement)
    jan = result.bill.monthly[0]
    assert jan.energy_charge == pytest.approx(70.0)
    assert jan.fixed_charge == pytest.approx(10.0)
    assert jan.total == pytest.approx(80.0)
    assert result.annual_credit_applied == pytest.approx(30.0)
    assert result.annual_credit_unused == pytest.approx(0.0)


def test_credit_in_excess_of_charge_caps_at_zero_energy_then_rolls_forward() -> None:
    """$50 charge + $80 credit → $0 energy charge (capped); $30 rolls
    to next month, where it offsets that month's $50 charge → $20 net."""
    charges = [50.0, 50.0] + [0.0] * 10
    credits = [80.0, 0.0] + [0.0] * 10
    result = compute_nbt_net_bill(
        annual_bill=_bill(charges),
        export_credit=_credit(credits),
    )

    jan = result.bill.monthly[0]
    feb = result.bill.monthly[1]
    assert jan.energy_charge == pytest.approx(0.0)
    assert feb.energy_charge == pytest.approx(20.0)
    assert result.annual_credit_applied == pytest.approx(80.0)
    assert result.annual_credit_unused == pytest.approx(0.0)


def test_year_end_zero_out_forfeits_unused_surplus() -> None:
    """Single big credit in November with no December charge → surplus
    is reported as ``annual_credit_unused`` and not silently rolled
    into the next year."""
    charges = [0.0] * 12  # zero usage — nothing to offset
    credits = [0.0] * 11 + [200.0]  # December credit
    result = compute_nbt_net_bill(
        annual_bill=_bill(charges, fixed=10.0),
        export_credit=_credit(credits),
    )

    assert result.annual_credit_applied == pytest.approx(0.0)
    assert result.annual_credit_unused == pytest.approx(200.0)
    # Fixed charges still bill — credit can't offset them per CPUC.
    assert result.bill.annual_fixed_charge == pytest.approx(120.0)
    assert result.bill.annual_total == pytest.approx(120.0)


def test_negative_credit_month_charges_customer_in_month() -> None:
    """CPUC spring-glut hours can yield negative monthly credit. The
    deficit gets settled the same month rather than carrying as debt
    into the next."""
    charges = [50.0, 50.0] + [0.0] * 10
    credits = [-10.0, 0.0] + [0.0] * 10
    result = compute_nbt_net_bill(
        annual_bill=_bill(charges),
        export_credit=_credit(credits),
    )

    jan = result.bill.monthly[0]
    feb = result.bill.monthly[1]
    # January: $50 charge + $10 export-debit = $60 net.
    assert jan.energy_charge == pytest.approx(60.0)
    # February: not affected — debt didn't carry forward.
    assert feb.energy_charge == pytest.approx(50.0)
    assert result.annual_credit_applied == pytest.approx(-10.0)
    assert result.annual_credit_unused == pytest.approx(0.0)


def test_rollover_offsets_subsequent_negative_credit_month() -> None:
    """Surplus from January absorbs February's negative-credit deficit:
    Jan $30 charge + $50 credit = $0 net, $20 rolls;
    Feb $40 charge + (-$5 credit) → net available $15, applied to charge → $25 net.
    """
    charges = [30.0, 40.0] + [0.0] * 10
    credits = [50.0, -5.0] + [0.0] * 10
    result = compute_nbt_net_bill(
        annual_bill=_bill(charges),
        export_credit=_credit(credits),
    )

    jan = result.bill.monthly[0]
    feb = result.bill.monthly[1]
    assert jan.energy_charge == pytest.approx(0.0)
    assert feb.energy_charge == pytest.approx(25.0)
    assert result.annual_credit_unused == pytest.approx(0.0)


def test_fixed_charge_is_never_offset_by_credit() -> None:
    """Per CPUC NBT rules, only the *energy* portion of the bill is
    creditable. Fixed monthly charges always bill — even when credit
    far exceeds total energy charges."""
    charges = [50.0] * 12
    credits = [500.0] * 12  # massive surplus
    result = compute_nbt_net_bill(
        annual_bill=_bill(charges, fixed=15.0),
        export_credit=_credit(credits),
    )

    for m in result.bill.monthly:
        assert m.fixed_charge == pytest.approx(15.0)
    assert result.bill.annual_fixed_charge == pytest.approx(15.0 * 12)
    # All energy charges fully offset; surplus is huge and forfeited.
    assert result.bill.annual_energy_charge == pytest.approx(0.0)
    assert result.annual_credit_applied == pytest.approx(50.0 * 12)
    expected_unused = 500.0 * 12 - 50.0 * 12
    assert result.annual_credit_unused == pytest.approx(expected_unused)


def test_rejects_non_nbt_regime() -> None:
    """SEG / NEM-1:1 regimes have different settlement rules; the helper
    refuses them rather than silently producing a wrong-shape bill."""
    bill = _bill([0.0] * 12)
    seg = ExportCreditResult(
        regime="seg_flat",
        monthly_credit=[0.0] * 12,
        annual_credit=0.0,
        annual_kwh_exported=0.0,
    )
    with pytest.raises(ValueError, match="nem_three_nbt"):
        compute_nbt_net_bill(annual_bill=bill, export_credit=seg)


def test_preserves_kwh_imported_and_currency_metadata() -> None:
    """Netting touches charge dollars, not the import volumes or the
    bill's currency — those are properties of the underlying physical
    bill that survive the netting pass."""
    bill = _bill([100.0] * 12)
    credit = _credit([20.0] * 12)
    result = compute_nbt_net_bill(annual_bill=bill, export_credit=credit)

    assert result.bill.currency == "USD"
    assert result.bill.annual_kwh_imported == pytest.approx(bill.annual_kwh_imported)
    for original, netted in zip(bill.monthly, result.bill.monthly, strict=True):
        assert original.kwh_imported == netted.kwh_imported
