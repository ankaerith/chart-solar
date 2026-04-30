"""UK SEG (Smart Export Guarantee) annual settlement netting.

UK SEG suppliers settle every 6 or 12 months. Two shapes matter:

* **SEG-flat** — single £/kWh rate, supplier pays regardless of import.
  Octopus Outgoing flat, E.ON Next, Bulb. Behaves as a straight credit
  against the year's bill; surplus pays out as cash, so there is no
  rollover or zero-out. We even-spread the credit across 12 months so
  per-month bills stay coherent in the UI.

* **SEG-TOU** — hourly TOU rate (Octopus Agile-style). Mirrors the
  NBT within-month + roll-forward + year-end-zero math. The one
  divergence from CPUC NBT is the lack of an NSC equivalent: UK
  suppliers either pay surplus or forfeit per contract, but there
  isn't a regulator-set Net Surplus Compensation rate to apply against
  ``annual_credit_unused``.

Sibling of ``backend.engine.integration.nbt.compute_nbt_net_bill``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.engine.steps.export_credit import ExportCreditResult
from backend.engine.steps.tariff import AnnualBill, MonthlyBill


class SegSettlement(BaseModel):
    """Post-netting bill plus the rollover bookkeeping the audit shows.

    ``bill`` is the post-netting :class:`AnnualBill` — each month's
    ``energy_charge`` already has applied credit subtracted.
    ``annual_credit_applied`` is the total credit that actually
    reduced the customer's bills this year (signed: negative when
    SEG-TOU rate-vector dips drove in-month deficits — rare in
    practice but the math admits it).
    ``annual_credit_unused`` carries SEG-TOU's year-end zero-out
    surplus *or* SEG-flat's supplier payout-to-homeowner — both
    represent credit the supplier did not absorb against the import
    bill. The SEG-flat case is cash the supplier owes; the SEG-TOU
    case is forfeit (UK suppliers don't expose an NSC-equivalent rate).
    """

    bill: AnnualBill
    annual_credit_applied: float
    annual_credit_unused: float = Field(..., ge=0.0)


def compute_seg_net_bill(
    *,
    annual_bill: AnnualBill,
    export_credit: ExportCreditResult,
) -> SegSettlement:
    """Net SEG export credit against an import bill.

    Routes by ``export_credit.regime``: SEG-flat is a one-shot
    passthrough (full annual credit applied, surplus paid out); SEG-TOU
    runs the NBT-style monthly rollover. Raises ``ValueError`` for any
    other regime — NEM 1:1 / NBT have their own integration helpers.
    """
    if export_credit.regime == "seg_flat":
        return _seg_flat_settlement(annual_bill=annual_bill, export_credit=export_credit)
    if export_credit.regime == "seg_tou":
        return _seg_tou_settlement(annual_bill=annual_bill, export_credit=export_credit)
    raise ValueError(
        "compute_seg_net_bill expects regime in {'seg_flat','seg_tou'} "
        f"(got {export_credit.regime!r})"
    )


def _seg_flat_settlement(
    *,
    annual_bill: AnnualBill,
    export_credit: ExportCreditResult,
) -> SegSettlement:
    """SEG-flat passthrough: distribute credit proportionally to each
    month's energy charge so ``annual_total - annual_credit`` falls out
    when credit ≤ energy bill, and any excess shows up as a supplier
    cash payout in ``annual_credit_unused``.

    Proportional (rather than even) distribution avoids leaving credit
    stranded on low-charge months — UK suppliers settle annually so
    the per-month split is presentational, but a faithful split keeps
    the audit's per-month visual honest.
    """
    annual_credit = export_credit.annual_credit
    annual_energy = annual_bill.annual_energy_charge
    if annual_energy <= 0:
        # Edge case: no import energy to apply against. The whole credit
        # is supplier payout; bill is unchanged.
        return SegSettlement(
            bill=annual_bill,
            annual_credit_applied=0.0,
            annual_credit_unused=max(0.0, annual_credit),
        )

    # Cap each month's allocation at its energy charge; surplus over the
    # whole year (annual_credit > annual_energy) becomes payout.
    netted: list[MonthlyBill] = []
    annual_applied = 0.0
    for m in annual_bill.monthly:
        share = annual_credit * (m.energy_charge / annual_energy)
        applied = min(share, m.energy_charge)
        annual_applied += applied
        net_energy = m.energy_charge - applied
        netted.append(
            MonthlyBill(
                month=m.month,
                kwh_imported=m.kwh_imported,
                energy_charge=net_energy,
                fixed_charge=m.fixed_charge,
                total=net_energy + m.fixed_charge,
            )
        )

    return SegSettlement(
        bill=AnnualBill(
            currency=annual_bill.currency,
            monthly=netted,
            annual_kwh_imported=annual_bill.annual_kwh_imported,
            annual_energy_charge=sum(m.energy_charge for m in netted),
            annual_fixed_charge=annual_bill.annual_fixed_charge,
            annual_total=sum(m.total for m in netted),
        ),
        annual_credit_applied=annual_applied,
        annual_credit_unused=max(0.0, annual_credit - annual_applied),
    )


def _seg_tou_settlement(
    *,
    annual_bill: AnnualBill,
    export_credit: ExportCreditResult,
) -> SegSettlement:
    """SEG-TOU monthly rollover: same shape as NBT, no NSC concept.

    Within-month: credit offsets that month's energy charge, surplus
    rolls forward, negative-credit hours settle in-month rather than
    accumulating debt across months. At year-end any rollover surplus
    forfeits — UK suppliers don't expose an NSC-equivalent payout rate
    on TOU SEG.
    """
    netted: list[MonthlyBill] = []
    rollover = 0.0
    annual_credit_applied = 0.0

    for bill_month, credit_month in zip(
        annual_bill.monthly,
        export_credit.monthly_credit,
        strict=True,
    ):
        available = rollover + credit_month  # signed
        if available >= 0:
            applied = min(available, bill_month.energy_charge)
            net_energy = bill_month.energy_charge - applied
            rollover = available - applied
            annual_credit_applied += applied
        else:
            # Negative balance settles in-month: customer pays the extra.
            net_energy = bill_month.energy_charge - available  # subtracts a negative
            annual_credit_applied += available  # signed (negative)
            rollover = 0.0

        netted.append(
            MonthlyBill(
                month=bill_month.month,
                kwh_imported=bill_month.kwh_imported,
                energy_charge=net_energy,
                fixed_charge=bill_month.fixed_charge,
                total=net_energy + bill_month.fixed_charge,
            )
        )

    return SegSettlement(
        bill=AnnualBill(
            currency=annual_bill.currency,
            monthly=netted,
            annual_kwh_imported=annual_bill.annual_kwh_imported,
            annual_energy_charge=sum(m.energy_charge for m in netted),
            annual_fixed_charge=annual_bill.annual_fixed_charge,
            annual_total=sum(m.total for m in netted),
        ),
        annual_credit_applied=annual_credit_applied,
        annual_credit_unused=rollover,
    )


__all__ = ["SegSettlement", "compute_seg_net_bill"]
