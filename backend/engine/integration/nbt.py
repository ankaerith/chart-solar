"""NEM 3.0 / NBT monthly true-up netting.

CPUC's Net Billing Tariff bills the customer for monthly retail
imports as usual, then *credits* their account at hourly avoided-cost
rates for any export. Within a billing cycle:

* Surplus credit offsets the energy portion of the import charge
  (fixed monthly charges are not creditable per CPUC rules).
* Any leftover credit rolls forward to the next month.
* If the hourly avoided-cost rate dips negative (CPUC spring glut),
  the customer is *charged* for export — that deficit is settled in
  the same month, not rolled forward.
* At the 12-month true-up boundary, leftover surplus credit is paid
  out at the Net Surplus Compensation rate (much lower than retail).
  We treat that as forfeit by default — callers monetising the
  surplus apply the NSC rate against ``annual_credit_unused``.

The same shape will eventually serve UK SEG annual settlement; the
helper isn't NBT-specific in math, only in the regime-tag check.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.engine.steps.export_credit import ExportCreditResult
from backend.engine.steps.tariff import AnnualBill, MonthlyBill


def run_monthly_rollover(
    *,
    annual_bill: AnnualBill,
    monthly_credit: list[float],
) -> tuple[AnnualBill, float, float]:
    """Apply ``monthly_credit`` against ``annual_bill`` with rollover.

    Returns ``(netted_bill, annual_credit_applied, annual_credit_unused)``.
    Within-month: credit offsets the energy portion of each month's bill,
    surplus rolls forward to the next month, negative-credit hours settle
    in-month rather than accumulating debt across months. Year-end leftover
    is the unused/forfeit balance.

    Shared with :func:`backend.engine.integration.seg._seg_tou_settlement`
    — the math is identical; what differs is the public wrapper's regime
    guard and the result type it constructs.
    """
    netted: list[MonthlyBill] = []
    rollover = 0.0
    annual_credit_applied = 0.0

    for bill_month, credit_month in zip(annual_bill.monthly, monthly_credit, strict=True):
        available = rollover + credit_month
        if available >= 0:
            applied = min(available, bill_month.energy_charge)
            net_energy = bill_month.energy_charge - applied
            rollover = available - applied
            annual_credit_applied += applied
        else:
            net_energy = bill_month.energy_charge - available
            annual_credit_applied += available
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

    netted_bill = AnnualBill(
        currency=annual_bill.currency,
        monthly=netted,
        annual_kwh_imported=annual_bill.annual_kwh_imported,
        annual_energy_charge=sum(m.energy_charge for m in netted),
        annual_fixed_charge=annual_bill.annual_fixed_charge,
        annual_total=sum(m.total for m in netted),
    )
    return netted_bill, annual_credit_applied, rollover


class NbtSettlement(BaseModel):
    """The netted bill plus the rollover bookkeeping the audit surfaces.

    ``bill`` is the post-netting :class:`AnnualBill` — each month's
    ``energy_charge`` already has applied credit subtracted (or
    negative-credit additions added). ``annual_credit_applied`` is the
    total credit that actually reduced the customer's bills this year
    (signed: negative when net spring-glut hours added to the bill).
    ``annual_credit_unused`` is the surplus zeroed out at year-end —
    callers wanting NSC monetisation multiply this by the NSC rate.
    """

    bill: AnnualBill
    annual_credit_applied: float
    annual_credit_unused: float = Field(..., ge=0.0)


def compute_nbt_net_bill(
    *,
    annual_bill: AnnualBill,
    export_credit: ExportCreditResult,
) -> NbtSettlement:
    """Net NBT export credit against an import bill, month-by-month.

    The credit can offset only the energy portion of each monthly bill
    (fixed monthly charges remain). Surplus rolls forward to the next
    month; any negative-credit balance settles in-month rather than
    accumulating debt across months. Year-end true-up zeros the rollover.

    Raises ``ValueError`` if ``export_credit.regime`` isn't ``nem_three_nbt``
    — the helper is regime-checked because the netting semantics here
    are CPUC-specific. UK SEG annual settlement will eventually share
    the math but lands behind a separate ``compute_seg_net_bill``.
    """
    if export_credit.regime != "nem_three_nbt":
        raise ValueError(
            f"compute_nbt_net_bill expects regime='nem_three_nbt' (got {export_credit.regime!r})"
        )

    netted_bill, applied, unused = run_monthly_rollover(
        annual_bill=annual_bill,
        monthly_credit=export_credit.monthly_credit,
    )
    return NbtSettlement(
        bill=netted_bill,
        annual_credit_applied=applied,
        annual_credit_unused=unused,
    )
