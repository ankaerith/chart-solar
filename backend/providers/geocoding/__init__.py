"""GeocodingProvider port — address ↔ coordinates.

Google Place ID is the launch adapter (per PRODUCT_PLAN.md § Tech
Stack); a `manual.py` (offline placeholder) lives alongside for tests
and dev environments without a Google API key.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class GeocodedLocation(BaseModel):
    """One geocoding result."""

    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    formatted_address: str
    country: str  # ISO-3166-1 alpha-2
    administrative_area: str | None = None  # e.g. "CA", "Greater London"
    locality: str | None = None  # city / town
    postal_code: str | None = None
    place_id: str | None = None  # Google place id where available


@runtime_checkable
class GeocodingProvider(Protocol):
    """Forward + reverse geocoding."""

    name: str

    async def geocode(self, address: str) -> GeocodedLocation: ...

    async def reverse(self, lat: float, lon: float) -> GeocodedLocation: ...


__all__ = ["GeocodedLocation", "GeocodingProvider"]
