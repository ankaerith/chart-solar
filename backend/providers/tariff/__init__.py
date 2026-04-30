"""TariffProvider port — retail energy tariffs.

The engine's tariff step (`backend/engine/steps/tariff.py`) consumes
`TariffSchedule` to bill an hourly net-load series. Providers are
responsible for *fetching* that schedule given a utility / zip. URDB +
Octopus + Manual adapters land in this subpackage as they're built
(`urdb.py`, `octopus.py`, `manual.py`); the engine only ever talks to
the `TariffProvider` Protocol so swapping in a new source is one DI
binding away.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, model_validator

CurrencyCode = Literal["USD", "GBP", "EUR"]
TariffStructure = Literal["flat", "tiered", "tou"]


class TouPeriod(BaseModel):
    """One time-of-use band. Rate applies during the hours where
    `hour_mask` is true on weekdays (`is_weekday=True`) or weekends
    (`is_weekday=False`)."""

    name: str
    rate_per_kwh: float = Field(..., ge=0.0)
    months: list[int] = Field(..., min_length=1, max_length=12)
    hour_mask: list[bool] = Field(..., min_length=24, max_length=24)
    is_weekday: bool = True

    @model_validator(mode="after")
    def _months_in_range(self) -> TouPeriod:
        for m in self.months:
            if not 1 <= m <= 12:
                raise ValueError(f"month {m} out of range 1..12")
        return self


class TieredBlock(BaseModel):
    """One tier in a stepped rate. Customer pays `rate_per_kwh` for the
    first `up_to_kwh_per_month` kWh; the next tier handles the rest.
    `up_to_kwh_per_month=None` is the catch-all top tier."""

    rate_per_kwh: float = Field(..., ge=0.0)
    up_to_kwh_per_month: float | None = Field(None, gt=0.0)


class TariffSchedule(BaseModel):
    """A retail energy tariff. The engine bills an hourly net-load
    series against this shape; the provider's job is to populate it."""

    name: str
    utility: str
    country: str = "US"
    currency: CurrencyCode = "USD"
    structure: TariffStructure = "flat"
    fixed_monthly_charge: float = Field(0.0, ge=0.0)

    flat_rate_per_kwh: float | None = Field(None, ge=0.0)
    tiered_blocks: list[TieredBlock] | None = None
    tou_periods: list[TouPeriod] | None = None

    @model_validator(mode="after")
    def _structure_consistency(self) -> TariffSchedule:
        if self.structure == "flat" and self.flat_rate_per_kwh is None:
            raise ValueError("flat tariff requires flat_rate_per_kwh")
        if self.structure == "tiered" and not self.tiered_blocks:
            raise ValueError("tiered tariff requires tiered_blocks")
        if self.structure == "tou" and not self.tou_periods:
            raise ValueError("tou tariff requires tou_periods")
        return self


class TariffQuery(BaseModel):
    """Lookup key. At least one of `utility` or `zip_code` should be
    set; providers fall back to a country-default if both are blank."""

    country: str = "US"
    utility: str | None = None
    zip_code: str | None = None


@runtime_checkable
class TariffProvider(Protocol):
    """Fetch a tariff schedule for a customer location."""

    name: str

    async def fetch(self, query: TariffQuery) -> TariffSchedule: ...


def first_matching_tou_period(
    periods: list[TouPeriod],
    *,
    month: int,
    is_weekday: bool,
    hour_of_day: int,
) -> TouPeriod | None:
    """First ``TouPeriod`` whose month list + weekday flag + hour mask
    cover the given hour, or ``None`` if no period matches.

    Authors of TOU schedules write non-overlapping bands, so first-match
    is a faithful read; any unmatched hour is a tariff-authoring bug.
    Callers wanting the rate read ``.rate_per_kwh`` from the result.
    """
    for period in periods:
        if month not in period.months:
            continue
        if period.is_weekday is not is_weekday:
            continue
        if period.hour_mask[hour_of_day]:
            return period
    return None


__all__ = [
    "CurrencyCode",
    "TariffProvider",
    "TariffQuery",
    "TariffSchedule",
    "TariffStructure",
    "TieredBlock",
    "TouPeriod",
    "first_matching_tou_period",
]
