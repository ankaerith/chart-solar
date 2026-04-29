"""MonitoringProvider port — third-party inverter / battery monitors.

Phase 4 (Track MVP) consumes hourly production from the homeowner's
monitoring vendor: Enphase, SolarEdge, Tesla CSV upload, GivEnergy.
Each gets its own subpackage adapter (`enphase.py`, `solaredge.py`,
`tesla_csv.py`, `givenergy.py`); the engine only sees this Protocol.

Credentials are intentionally `dict[str, str]` — every vendor has its
own auth shape (OAuth tokens, site keys, exported-CSV path), and the
engine doesn't care which one it is.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class MonitoringSite(BaseModel):
    """One physical site visible to a monitoring vendor."""

    site_id: str
    name: str
    timezone: str  # IANA tz
    dc_kw: float | None = Field(None, gt=0.0)
    install_date: date | None = None


class MonitoringReading(BaseModel):
    """One hourly production sample."""

    timestamp_utc: datetime
    energy_kwh: float = Field(..., ge=0.0)


@runtime_checkable
class MonitoringProvider(Protocol):
    """Read production data from an upstream monitoring vendor."""

    name: str

    async def list_sites(
        self,
        credential: dict[str, str],
    ) -> list[MonitoringSite]: ...

    async def fetch_production(
        self,
        credential: dict[str, str],
        site_id: str,
        start: date,
        end: date,
    ) -> list[MonitoringReading]: ...


__all__ = [
    "MonitoringProvider",
    "MonitoringReading",
    "MonitoringSite",
]
