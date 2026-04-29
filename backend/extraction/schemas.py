"""Pydantic tool-use schemas for proposal extraction.

The Gemini call uses `ExtractedProposal` as its structured-output schema;
every field is wrapped in `Extracted[T]` so the model can attach a
self-reported confidence and a `source_quote` (verbatim PDF span). The
audit pipeline then decides whether to surface low-confidence critical
fields for user correction.

Field inventory mirrors PRODUCT_PLAN.md § Extraction field inventory.
Every change here MUST stay aligned with that section — if you're
adding a field, add it there too.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Extracted[T](BaseModel):
    """One field plucked from the proposal, with the model's
    self-reported confidence and the verbatim PDF text it pulled from.

    `confidence` is in [0, 1]; `source_quote` is optional because some
    fields (totals, computed values) aren't a direct quote. `value` is
    nullable so the model can say "not stated in this proposal" without
    making something up — that's a feature, not a missing-data hack.
    """

    value: T | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_quote: str | None = None


# ---------------------------------------------------------------------------
# Equipment
# ---------------------------------------------------------------------------

InverterType = Literal["string", "microinverter", "hybrid"]
MountingType = Literal["roof", "ground"]


class PanelEquipment(BaseModel):
    manufacturer: Extracted[str]
    model: Extracted[str]
    rated_watts_stc: Extracted[float]
    warranty_years: Extracted[int]


class InverterEquipment(BaseModel):
    make: Extracted[str]
    model: Extracted[str]
    type: Extracted[InverterType]
    rated_kw: Extracted[float]


class BatteryEquipment(BaseModel):
    """Optional — only populated when the proposal includes storage."""

    make: Extracted[str]
    model: Extracted[str]
    usable_kwh: Extracted[float]
    nameplate_kwh: Extracted[float] | None = None
    backup_capable: Extracted[bool]


class SystemEquipment(BaseModel):
    panel: PanelEquipment
    panel_count: Extracted[int]
    total_dc_kw: Extracted[float]
    total_ac_kw: Extracted[float]
    inverter: InverterEquipment
    optimizers_present: Extracted[bool]
    rapid_shutdown_present: Extracted[bool]
    battery: BatteryEquipment | None = None
    mounting_type: Extracted[MountingType]
    tilt_deg: Extracted[float] | None = None
    azimuth_deg: Extracted[float] | None = None
    monitoring_platform: Extracted[str] | None = None
    monitoring_years_included: Extracted[int] | None = None


# ---------------------------------------------------------------------------
# Financial
# ---------------------------------------------------------------------------

LineItemKind = Literal["adder", "fee", "tax", "cost", "discount"]
IncentiveClaimType = Literal[
    "federal_itc",
    "state_credit",
    "utility_rebate",
    "srec",
    "uk_seg",
]
FinancingMethod = Literal["cash", "loan", "ppa", "lease", "subscription"]


class LineItem(BaseModel):
    """One adder / fee / tax line on the proposal."""

    name: str
    amount: float
    kind: LineItemKind


class IncentiveClaim(BaseModel):
    """An incentive the proposal claims (independent of whether it's
    actually applicable — that's the audit engine's job)."""

    name: str
    type: IncentiveClaimType
    amount: float = Field(..., ge=0.0)


class Financing(BaseModel):
    method: FinancingMethod
    term_years: int | None = Field(None, gt=0)
    apr: float | None = Field(None, ge=0.0, le=1.0)
    dealer_fee: float | None = Field(None, ge=0.0)
    monthly_payment: float | None = Field(None, ge=0.0)
    ppa_escalator: float | None = Field(None, ge=-1.0, le=1.0)
    ppa_buyout: float | None = Field(None, ge=0.0)


class Financial(BaseModel):
    gross_system_price: Extracted[float]
    dollar_per_watt: Extracted[float]
    line_items: list[LineItem] = Field(default_factory=list)
    incentives_claimed: list[IncentiveClaim] = Field(default_factory=list)
    net_price_after_incentives: Extracted[float]
    financing: Extracted[Financing]
    assumed_escalator: Extracted[float] | None = None
    assumed_degradation: Extracted[float] | None = None
    year_1_kwh_claim: Extracted[float]
    twenty_year_savings_claim: Extracted[float] | None = None
    payback_year_claimed: Extracted[float] | None = None


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------


class Installer(BaseModel):
    """Company-level + sales-rep info. Per LEGAL_CONSIDERATIONS.md F1
    sales-rep direct PII (phone, email) is stripped at extraction; we
    only retain rep *name* + company-level data."""

    company_name: Extracted[str]
    license_number: Extracted[str] | None = None
    address: Extracted[str] | None = None
    phone: Extracted[str] | None = None
    rep_name: Extracted[str] | None = None
    quote_date: Extracted[date]
    expiration_date: Extracted[date] | None = None
    nabcep_certified: Extracted[bool] | None = None
    installation_timeline_weeks: Extracted[int] | None = None
    workmanship_warranty_years: Extracted[int] | None = None


# ---------------------------------------------------------------------------
# Operational
# ---------------------------------------------------------------------------

ProductionEstimateSource = Literal[
    "pvwatts",
    "aurora",
    "installer_proprietary",
    "other",
    "not_disclosed",
]


class Operational(BaseModel):
    shading_assumption: Extracted[str] | None = None
    production_estimate_source: Extracted[ProductionEstimateSource]
    monitoring_years_free: Extracted[int] | None = None
    service_agreement_terms: Extracted[str] | None = None


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------


class ExtractedProposal(BaseModel):
    """Top-level Gemini structured-output target.

    `overall_confidence` is the model's roll-up; the audit pipeline can
    second-guess it via `critical_field_confidences()` which looks at
    individual field confidences directly. `needs_stronger_model` is the
    model's self-declared escalation hint — combined with our
    deterministic floor (file size, scan-vs-digital, etc.) to decide
    whether to retry against Gemini 3 Flash / Pro per PRODUCT_PLAN.md
    § Extraction engine.
    """

    system: SystemEquipment
    financial: Financial
    installer: Installer
    operational: Operational
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    needs_stronger_model: bool = False
    extraction_notes: str | None = None
