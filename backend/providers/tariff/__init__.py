"""TariffProvider port — retail energy tariffs.

The engine's tariff step (`backend/engine/steps/tariff.py`) consumes
`TariffSchedule` to bill an hourly net-load series. Providers are
responsible for *fetching* that schedule given a utility / zip. URDB +
Octopus + Manual adapters land in this subpackage as they're built
(`urdb.py`, `octopus.py`, `manual.py`); the engine only ever talks to
the `TariffProvider` Protocol so swapping in a new source is one DI
binding away.

The shared shapes (``TariffSchedule``, ``TouPeriod``, ``TieredBlock``,
``CurrencyCode``, ``TariffStructure``, ``first_matching_tou_period``)
live in ``backend.domain.tariff``. They're re-exported here for
backward compatibility; new code should import from
``backend.domain.tariff`` directly.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from backend.domain.tariff import (
    CurrencyCode,
    TariffSchedule,
    TariffStructure,
    TieredBlock,
    TouPeriod,
    first_matching_tou_period,
)


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
