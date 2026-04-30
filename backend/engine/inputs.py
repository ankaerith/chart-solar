"""Pydantic schemas for engine inputs.

Each top-level input group maps to a section of the modeling pipeline.
The pipeline orchestrator (``backend.engine.pipeline``) walks the
registered steps in canonical order and reads only the fields each step
needs — fields here are intentionally optional so the chain runs in
degenerate forms (no consumption ⇒ all production exports; no tariff
schedule ⇒ tariff + export-credit steps are skipped; no system cost ⇒
the finance step is skipped).

The export-credit regime configs live here (rather than under
``engine.steps.export_credit``) because eager-loading ``engine.steps``
re-enters this module via ``dc_production`` etc. — keeping the config
shapes at the IO boundary breaks that cycle. Each variant's ``apply()``
method imports the engine math lazily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from backend.engine.types import ExportRegime
from backend.providers.irradiance import HOURS_PER_TMY
from backend.providers.tariff import TariffSchedule

if TYPE_CHECKING:
    from backend.engine.steps.export_credit import ExportCreditResult


__all__ = [
    "ConsumptionInputs",
    "ExportCreditConfig",
    "ExportRegime",
    "FinancialInputs",
    "ForecastInputs",
    "LoanInputs",
    "NbtConfig",
    "NemOneForOneConfig",
    "SegFlatConfig",
    "SegTouConfig",
    "SystemInputs",
    "TariffInputs",
]


class NemOneForOneConfig(BaseModel):
    """NEM 1:1 retail-rate netting. Reads back the import tariff."""

    regime: Literal["nem_one_for_one"] = "nem_one_for_one"

    def apply(
        self,
        *,
        hourly_export_kwh: list[float],
        tariff: TariffSchedule | None = None,
        hourly_net_load_kwh: list[float] | None = None,
    ) -> ExportCreditResult:
        from backend.engine.steps.export_credit import apply_nem_one_for_one

        if tariff is None:
            raise ValueError("nem_one_for_one regime requires `tariff`")
        return apply_nem_one_for_one(
            hourly_export_kwh=hourly_export_kwh,
            tariff=tariff,
            hourly_net_load_kwh=hourly_net_load_kwh,
        )


class NbtConfig(BaseModel):
    """California NEM 3.0 / NBT. Credits at the CPUC ACC vector."""

    regime: Literal["nem_three_nbt"] = "nem_three_nbt"
    hourly_avoided_cost_per_kwh: list[float] = Field(
        ..., min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY
    )

    def apply(
        self,
        *,
        hourly_export_kwh: list[float],
        tariff: TariffSchedule | None = None,
        hourly_net_load_kwh: list[float] | None = None,
    ) -> ExportCreditResult:
        from backend.engine.steps.export_credit import apply_nem_three_nbt

        return apply_nem_three_nbt(
            hourly_export_kwh=hourly_export_kwh,
            hourly_avoided_cost_per_kwh=self.hourly_avoided_cost_per_kwh,
        )


class SegFlatConfig(BaseModel):
    """UK SEG with a single flat supplier rate."""

    regime: Literal["seg_flat"] = "seg_flat"
    flat_rate_per_kwh: float = Field(..., ge=0.0)

    def apply(
        self,
        *,
        hourly_export_kwh: list[float],
        tariff: TariffSchedule | None = None,
        hourly_net_load_kwh: list[float] | None = None,
    ) -> ExportCreditResult:
        from backend.engine.steps.export_credit import apply_seg_flat

        return apply_seg_flat(
            hourly_export_kwh=hourly_export_kwh,
            rate_per_kwh=self.flat_rate_per_kwh,
        )


class SegTouConfig(BaseModel):
    """UK SEG with an hourly TOU rate vector (Octopus Agile-style)."""

    regime: Literal["seg_tou"] = "seg_tou"
    hourly_rate_per_kwh: list[float] = Field(
        ..., min_length=HOURS_PER_TMY, max_length=HOURS_PER_TMY
    )

    def apply(
        self,
        *,
        hourly_export_kwh: list[float],
        tariff: TariffSchedule | None = None,
        hourly_net_load_kwh: list[float] | None = None,
    ) -> ExportCreditResult:
        from backend.engine.steps.export_credit import apply_seg_tou

        return apply_seg_tou(
            hourly_export_kwh=hourly_export_kwh,
            hourly_rate_per_kwh=self.hourly_rate_per_kwh,
        )


#: Discriminated union over regime configs. Pydantic dispatches on
#: ``regime`` at parse time so bad regime/field combinations fail
#: before reaching the engine.
ExportCreditConfig = Annotated[
    NemOneForOneConfig | NbtConfig | SegFlatConfig | SegTouConfig,
    Field(discriminator="regime"),
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
    collapses to even principal split (zero-interest dealer offers).

    For variable-rate products (HELOCs, ARM loans), pass
    ``monthly_rates`` instead — a per-month rate vector of length
    ``term_months``. Exactly one of ``apr`` / ``monthly_rates`` must
    be set; the engine routes through ``amortize`` or
    ``amortize_variable`` accordingly.
    """

    principal: float = Field(..., gt=0.0)
    apr: float | None = Field(None, ge=0.0, le=0.50)
    monthly_rates: list[float] | None = Field(None, min_length=1)
    term_months: int = Field(..., ge=1, le=600)
    down_payment: float = Field(0.0, ge=0.0)

    @model_validator(mode="after")
    def _exactly_one_rate_form(self) -> LoanInputs:
        if (self.apr is None) == (self.monthly_rates is None):
            raise ValueError("LoanInputs requires exactly one of `apr` or `monthly_rates`")
        if self.monthly_rates is not None and len(self.monthly_rates) != self.term_months:
            raise ValueError(
                f"monthly_rates length ({len(self.monthly_rates)}) "
                f"must equal term_months ({self.term_months})"
            )
        return self


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


class TariffInputs(BaseModel):
    country: str = Field("US", min_length=2, max_length=2)
    utility: str | None = None
    schedule: TariffSchedule | None = None
    export_credit: ExportCreditConfig | None = None


DispatchStrategy = Literal["self_consumption", "tou_arbitrage"]


class BatteryInputs(BaseModel):
    """Battery system parameters for the rule-based dispatch step.

    Defaults are tuned to a typical residential lithium-ion install
    (e.g. Powerwall 3): 13.5 kWh nameplate, ~95 % usable, ~90 %
    round-trip efficiency, max ~5 kW continuous, and a 20 % reserve
    held back for backup. Override any of these to fit a specific
    product spec.

    ``strategy`` selects the rule-based dispatch policy:

    * ``self_consumption`` — charge whenever solar exports, discharge
      to cover any import need. Maximises self-use, ignores tariff.
    * ``tou_arbitrage`` — charge only off-peak, discharge only on-peak
      (peak / off-peak inferred from the active TOU schedule). Falls
      back to self-consumption when the schedule isn't TOU-shaped.
    """

    capacity_kwh: float = Field(13.5, gt=0.0)
    usable_pct: float = Field(0.95, gt=0.0, le=1.0)
    round_trip_efficiency: float = Field(0.90, gt=0.0, le=1.0)
    max_charge_kw: float = Field(5.0, gt=0.0)
    max_discharge_kw: float = Field(5.0, gt=0.0)
    reserve_pct: float = Field(0.20, ge=0.0, le=1.0)
    strategy: DispatchStrategy = "self_consumption"


class ForecastInputs(BaseModel):
    system: SystemInputs
    financial: FinancialInputs
    tariff: TariffInputs
    consumption: ConsumptionInputs | None = None
    battery: BatteryInputs | None = None
