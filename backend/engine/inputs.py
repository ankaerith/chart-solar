"""Pydantic schemas for engine inputs.

Each top-level input group maps to a section of the modeling pipeline.
The pipeline orchestrator (``backend.engine.pipeline``) walks the
registered steps in canonical order and reads only the fields each step
needs — fields here are intentionally optional so the chain runs in
degenerate forms (no consumption ⇒ all production exports; no tariff
schedule ⇒ tariff + export-credit steps are skipped; no system cost ⇒
the finance step is skipped).
"""

from pydantic import BaseModel, Field

from backend.engine.types import ExportRegime
from backend.providers.irradiance import HOURS_PER_TMY
from backend.providers.tariff import TariffSchedule

__all__ = [
    "ConsumptionInputs",
    "ExportCreditInputs",
    "ExportRegime",
    "FinancialInputs",
    "ForecastInputs",
    "LoanInputs",
    "SystemInputs",
    "TariffInputs",
]


class SystemInputs(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    dc_kw: float = Field(..., gt=0, le=50)
    tilt_deg: float = Field(..., ge=0, le=90)
    azimuth_deg: float = Field(..., ge=0, le=360)


class LoanInputs(BaseModel):
    """Optional financing for the system. Year-0 cashflow becomes
    ``-down_payment`` instead of ``-system_cost``; each subsequent year
    deducts the sum of that year's twelve monthly payments. ``apr=0``
    collapses to even principal split (zero-interest dealer offers)."""

    principal: float = Field(..., gt=0.0)
    apr: float = Field(..., ge=0.0, le=0.50)
    term_months: int = Field(..., ge=1, le=600)
    down_payment: float = Field(0.0, ge=0.0)


class FinancialInputs(BaseModel):
    """Financial assumptions for the finance step. ``system_cost`` is
    optional so the pipeline degrades gracefully — the finance step is
    skipped when no capex is supplied (early Phase-1a smoke tests run
    without finance)."""

    discount_rate: float = Field(0.06, ge=0, le=0.30)
    hold_years: int = Field(15, ge=1, le=40)
    system_cost: float | None = Field(None, ge=0.0)
    annual_opex: float = Field(0.0, ge=0.0)
    rate_escalation: float = Field(0.025, ge=-0.10, le=0.20)
    loan: LoanInputs | None = None


class ConsumptionInputs(BaseModel):
    """Household load profile.

    ``hourly_kwh`` is the source of truth when present (8760 entries,
    same calendar anchor as ``TmyData``). ``annual_kwh`` is a coarse
    fallback for early integrations: the pipeline spreads it evenly
    across the year so net-load math still goes through. Real load
    shapes (ResStock archetypes, Green Button imports) replace the
    even-split fallback once the consumption step lands fully.
    """

    hourly_kwh: list[float] | None = Field(None, min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY)
    annual_kwh: float | None = Field(None, ge=0.0)


class ExportCreditInputs(BaseModel):
    """Regime + the regime-specific data the export-credit step needs.

    Each export-credit regime consumes a different shape of rate data:
    NEM 1:1 reads back the import tariff (no extra fields here), NBT
    needs the CPUC ACC vector, SEG-flat a scalar, SEG-TOU an hourly
    vector. Required-vs-not is enforced by the dispatcher in
    ``engine.steps.export_credit`` — these inputs are deliberately
    optional so the schema can travel with any regime.
    """

    regime: ExportRegime
    hourly_avoided_cost_per_kwh: list[float] | None = Field(
        None, min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY
    )
    flat_rate_per_kwh: float | None = Field(None, ge=0.0)
    hourly_rate_per_kwh: list[float] | None = Field(
        None, min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY
    )


class TariffInputs(BaseModel):
    country: str = Field("US", min_length=2, max_length=2)
    utility: str | None = None
    schedule: TariffSchedule | None = None
    export_credit: ExportCreditInputs | None = None


class ForecastInputs(BaseModel):
    system: SystemInputs
    financial: FinancialInputs
    tariff: TariffInputs
    consumption: ConsumptionInputs | None = None
