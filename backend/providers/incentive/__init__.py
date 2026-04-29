"""IncentiveProvider port — date-parameterized, jurisdiction-scoped.

The engine's finance roll-up consumes a list of `Incentive`s applicable
to a given install. Federal ITC + state credits + rebates + SRECs +
UK SEG live behind this Protocol; concrete adapters (manual curated
table at launch, DSIRE later) land in subpackage modules.
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

IncentiveType = Literal[
    "federal_itc",
    "state_credit",
    "utility_rebate",
    "srec",
    "uk_seg",
    "feed_in",
]
IncentiveAmountKind = Literal[
    "pct_system_cost",
    "fixed_amount",
    "per_kwh",
    "per_w_dc",
]


class Incentive(BaseModel):
    """One incentive line item."""

    name: str
    type: IncentiveType
    jurisdiction: str  # ISO-3166-2 (e.g. "US-CA") or country code "GB"
    amount: float = Field(..., ge=0.0)
    amount_kind: IncentiveAmountKind
    start_date: date | None = None
    end_date: date | None = None
    cap_amount: float | None = Field(None, ge=0.0)


class IncentiveQuery(BaseModel):
    """Lookup parameters for which incentives apply to one install."""

    jurisdiction: str
    install_date: date
    system_cost: float | None = Field(None, ge=0.0)
    system_dc_kw: float | None = Field(None, gt=0.0)


@runtime_checkable
class IncentiveProvider(Protocol):
    """Return every incentive a system qualifies for at install time."""

    name: str

    async def fetch(self, query: IncentiveQuery) -> list[Incentive]: ...


__all__ = [
    "Incentive",
    "IncentiveAmountKind",
    "IncentiveProvider",
    "IncentiveQuery",
    "IncentiveType",
]
