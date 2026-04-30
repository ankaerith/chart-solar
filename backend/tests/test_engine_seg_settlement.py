"""UK SEG annual settlement netting (chart-solar-cm50).

Pins the integration semantics between the standalone tariff bill
(``engine.tariff``) and the SEG export credit (``engine.export_credit``):
flat-rate passthrough, TOU within-month rollover, year-end zero-out,
regime guard against NEM regimes.
"""

from __future__ import annotations

import pytest

from backend.engine.integration.seg import (
    SegSettlement,
    compute_seg_net_bill,
)
from backend.engine.steps.export_credit import ExportCreditResult
from backend.engine.steps.tariff import AnnualBill, MonthlyBill


def _bill(monthly_charges: list[float], *, fixed: float = 5.0, currency: str = "GBP") -> AnnualBill:
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
        currency=currency,
        monthly=monthly,
        annual_kwh_imported=sum(m.kwh_imported for m in monthly),
        annual_energy_charge=sum(monthly_charges),
        annual_fixed_charge=fixed * 12,
        annual_total=sum(m.total for m in monthly),
    )


def _credit(monthly_credits: list[float], *, regime: str) -> ExportCreditResult:
    if len(monthly_credits) != 12:
        raise AssertionError("provide 12 monthly credits")
    return ExportCreditResult(
        regime=regime,
        monthly_credit=monthly_credits,
        annual_credit=sum(monthly_credits),
        annual_kwh_exported=1000.0,
    )


# --- SEG-flat ---------------------------------------------------------


def test_seg_flat_applies_full_credit_with_no_rollover() -> None:
    """SEG-flat suppliers pay regardless of import. The full annual
    credit reduces the bill; no surplus is forfeit."""
    bill = _bill([60.0] * 12)  # £720 energy, £60 fixed → £780 total
    credit = _credit([10.0] * 12, regime="seg_flat")  # £120 annual credit

    result = compute_seg_net_bill(annual_bill=bill, export_credit=credit)

    assert isinstance(result, SegSettlement)
    assert result.annual_credit_applied == pytest.approx(120.0)
    assert result.annual_credit_unused == pytest.approx(0.0)
    # Bill - credit = 780 - 120 = 660. Each month is 60+5-10 = 55.
    assert result.bill.annual_total == pytest.approx(660.0)
    for m in result.bill.monthly:
        assert m.energy_charge == pytest.approx(50.0)
        assert m.total == pytest.approx(55.0)


def test_seg_flat_credit_exceeding_bill_caps_at_zero_energy_with_surplus_payout() -> None:
    """Octopus Outgoing-style: when annual credit > annual energy
    charge, the bill's energy line zeroes out and the rest becomes a
    supplier cash payout — recorded as ``annual_credit_unused`` (the
    field doubles as 'credit not absorbed by the import bill')."""
    bill = _bill([10.0] * 12)  # £120 energy, £60 fixed → £180 total
    credit = _credit([30.0] * 12, regime="seg_flat")  # £360 annual credit

    result = compute_seg_net_bill(annual_bill=bill, export_credit=credit)

    # Energy is fully zeroed (£120 absorbed); the remaining £240 is
    # payout to the homeowner.
    assert result.annual_credit_applied == pytest.approx(120.0)
    assert result.annual_credit_unused == pytest.approx(240.0)
    # Bill drops to fixed_charge total: £60.
    assert result.bill.annual_energy_charge == pytest.approx(0.0)
    assert result.bill.annual_total == pytest.approx(60.0)


def test_seg_flat_zero_credit_leaves_bill_unchanged() -> None:
    bill = _bill([20.0] * 12)
    credit = _credit([0.0] * 12, regime="seg_flat")
    result = compute_seg_net_bill(annual_bill=bill, export_credit=credit)
    assert result.annual_credit_applied == pytest.approx(0.0)
    assert result.bill.annual_total == pytest.approx(bill.annual_total)


# --- SEG-TOU (mirrors NBT semantics) ----------------------------------


def test_seg_tou_within_month_netting_reduces_energy_charge() -> None:
    bill = _bill([100.0] + [0.0] * 11)
    credit = _credit([30.0] + [0.0] * 11, regime="seg_tou")
    result = compute_seg_net_bill(annual_bill=bill, export_credit=credit)

    jan = result.bill.monthly[0]
    assert jan.energy_charge == pytest.approx(70.0)
    assert jan.total == pytest.approx(75.0)
    assert result.annual_credit_applied == pytest.approx(30.0)
    assert result.annual_credit_unused == pytest.approx(0.0)


def test_seg_tou_summer_glut_rolls_forward_to_winter() -> None:
    """Big summer credit, big winter import: the surplus from June
    offsets January's bill entirely (after rolling through the
    intervening months)."""
    charges = [200.0] + [0.0] * 5 + [0.0] * 5 + [200.0]
    credits = [0.0] * 5 + [400.0] + [0.0] * 6  # June only

    result = compute_seg_net_bill(
        annual_bill=_bill(charges),
        export_credit=_credit(credits, regime="seg_tou"),
    )

    # June absorbs 0 (no charge), rolls 400 forward.
    # July-Nov are all 0/0, rollover stays at 400.
    # Dec consumes 200 from rollover → energy 0, rollover 200 unused.
    dec = result.bill.monthly[11]
    assert dec.energy_charge == pytest.approx(0.0)
    assert result.annual_credit_applied == pytest.approx(200.0)
    assert result.annual_credit_unused == pytest.approx(200.0)
    # Jan was before the credit arrived → unchanged.
    jan = result.bill.monthly[0]
    assert jan.energy_charge == pytest.approx(200.0)


def test_seg_tou_negative_credit_settles_in_month() -> None:
    """If the TOU rate vector dips negative in a month (rate-vector
    glitch / settlement adjustment), the customer pays the extra in
    that month rather than accumulating debt across months."""
    charges = [100.0, 100.0] + [0.0] * 10
    credits = [-20.0, 30.0] + [0.0] * 10  # Jan adds £20 to bill

    result = compute_seg_net_bill(
        annual_bill=_bill(charges),
        export_credit=_credit(credits, regime="seg_tou"),
    )

    # Jan: 100 - (-20) = 120 energy.
    assert result.bill.monthly[0].energy_charge == pytest.approx(120.0)
    # Feb: 100 - 30 = 70 (Jan's deficit didn't carry).
    assert result.bill.monthly[1].energy_charge == pytest.approx(70.0)
    # Net applied = -20 (Jan deficit) + 30 (Feb credit) = 10.
    assert result.annual_credit_applied == pytest.approx(10.0)


def test_seg_tou_year_end_surplus_zeroes_out() -> None:
    """At year-end any rolled-forward surplus forfeits — UK SEG-TOU
    has no NSC equivalent so the audit just reports it as unused."""
    charges = [0.0] * 12
    credits = [50.0] + [0.0] * 11  # £50 with no bill to apply against

    result = compute_seg_net_bill(
        annual_bill=_bill(charges),
        export_credit=_credit(credits, regime="seg_tou"),
    )

    assert result.annual_credit_applied == pytest.approx(0.0)
    assert result.annual_credit_unused == pytest.approx(50.0)


# --- regime guard -----------------------------------------------------


def test_rejects_nem_one_for_one_regime() -> None:
    bill = _bill([0.0] * 12)
    credit = _credit([0.0] * 12, regime="nem_one_for_one")
    with pytest.raises(ValueError, match="seg_flat"):
        compute_seg_net_bill(annual_bill=bill, export_credit=credit)


def test_rejects_nem_three_nbt_regime() -> None:
    bill = _bill([0.0] * 12)
    credit = _credit([0.0] * 12, regime="nem_three_nbt")
    with pytest.raises(ValueError, match="seg_flat"):
        compute_seg_net_bill(annual_bill=bill, export_credit=credit)
