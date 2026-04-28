"""Pydantic schemas for engine inputs.

Each top-level input group maps to a section of the modeling pipeline.
Real fields land in Phase 1a as steps come online; this is the contract.
"""

from pydantic import BaseModel, Field


class SystemInputs(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    dc_kw: float = Field(..., gt=0, le=50)
    tilt_deg: float = Field(..., ge=0, le=90)
    azimuth_deg: float = Field(..., ge=0, le=360)


class FinancialInputs(BaseModel):
    discount_rate: float = Field(0.06, ge=0, le=0.30)
    hold_years: int = Field(15, ge=1, le=40)


class TariffInputs(BaseModel):
    country: str = Field("US", min_length=2, max_length=2)
    utility: str | None = None


class ForecastInputs(BaseModel):
    system: SystemInputs
    financial: FinancialInputs
    tariff: TariffInputs
