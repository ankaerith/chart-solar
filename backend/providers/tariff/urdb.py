"""URDB-seeded ``TariffProvider``.

Loads a hand-curated snapshot of NREL's Utility Rate Database (URDB,
CC0) for the top-10 US residential utilities — PG&E, SCE, SDG&E, PSE,
Xcel CO, FPL, Duke NC, APS, SRP, ConEd. Each utility contributes its
default residential rate (typically TOU in CA, tiered in WA / CO / AZ,
flat elsewhere).

URDB lags real rate cases by weeks. The seed file embeds a
``snapshot_date`` and ``stale_warning_days`` window; ``UrdbSeedProvider``
exposes ``stale_after`` so callers can render a "rate may be outdated"
banner without re-deriving the policy at every render.

A live ``UrdbApiProvider`` (HTTP client against ``openei.org/services``)
lands separately — the seed provider is the offline-by-default path
that satisfies dev + CI without internet, and the launch-day fallback
when the API is unreachable.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date, timedelta
from functools import lru_cache
from importlib import resources
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from backend.providers.tariff import (
    CurrencyCode,
    TariffQuery,
    TariffSchedule,
    TariffStructure,
    TieredBlock,
    TouPeriod,
)

#: Resource path inside ``backend.providers.tariff`` for the seed file.
#: Pinned by name so a rotation (e.g. ``urdb_top10_2026q3.json``) is an
#: explicit code change, not a silent refresh.
SEED_RESOURCE_PACKAGE = "backend.providers.tariff.seed_data"
SEED_RESOURCE_FILENAME = "urdb_top10_2026q2.json"


class UrdbRateSeed(BaseModel):
    """One canonical residential rate per utility, as captured in the seed.

    The Pydantic model mirrors the JSON shape so a malformed seed fails
    at load time rather than at first ``.fetch()``.
    """

    utility_key: str
    utility_name: str
    country: str = "US"
    state: str
    rate_name: str
    urdb_label: str
    structure: TariffStructure
    currency: CurrencyCode = "USD"
    fixed_monthly_charge: float = 0.0
    flat_rate_per_kwh: float | None = None
    tiered_blocks: list[TieredBlock] | None = None
    tou_periods: list[TouPeriod] | None = None


class UrdbSeed(BaseModel):
    """The seed file's top-level shape."""

    schema_version: int = Field(..., ge=1)
    snapshot_date: date
    snapshot_label: str
    source: str
    refresh_cadence_days: int = Field(..., ge=1)
    stale_warning_days: int = Field(..., ge=1)
    notes: list[str] = Field(default_factory=list)
    rates: list[UrdbRateSeed]


def _flatten_utilities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """JSON groups rates under ``utilities[].rates[]``; the model carries
    them as a flat list so a single utility with multiple rates (Phase
    1b: time-of-day tiers, EV plans, etc.) doesn't require nesting at
    the model layer."""
    flat: list[dict[str, Any]] = []
    for utility in payload.get("utilities", []):
        for rate in utility.get("rates", []):
            flat.append(
                {
                    "utility_key": utility["key"],
                    "utility_name": utility["name"],
                    "country": utility.get("country", "US"),
                    "state": utility["state"],
                    **rate,
                    "rate_name": rate["name"],
                }
            )
    return flat


def _to_schedule(rate: UrdbRateSeed) -> TariffSchedule:
    """Project a seed row onto the engine's ``TariffSchedule`` shape.

    The seed's structure-specific fields (``flat_rate_per_kwh`` /
    ``tiered_blocks`` / ``tou_periods``) round-trip 1:1 into the
    schedule; ``model_validator`` on ``TariffSchedule`` enforces the
    structure ↔ payload coupling so a malformed snapshot fails loudly.
    """
    return TariffSchedule(
        name=rate.rate_name,
        utility=rate.utility_name,
        country=rate.country,
        currency=rate.currency,
        structure=rate.structure,
        fixed_monthly_charge=rate.fixed_monthly_charge,
        flat_rate_per_kwh=rate.flat_rate_per_kwh,
        tiered_blocks=rate.tiered_blocks,
        tou_periods=rate.tou_periods,
    )


@lru_cache(maxsize=1)
def load_seed() -> UrdbSeed:
    """Read the bundled JSON snapshot into a validated ``UrdbSeed``.

    Loads via ``importlib.resources`` so the file is found whether the
    package is checked out or installed from a wheel. Raises
    ``ValueError`` (not the bare Pydantic ``ValidationError``) so callers
    can catch one type for any seed-load failure.

    Cached because the snapshot is a build-time constant — re-reading
    the JSON on every ``UrdbSeedProvider`` instantiation would burn
    disk I/O for no benefit. The cache is invalidated automatically on
    ``SEED_RESOURCE_FILENAME`` rotation since the function is keyed on
    the symbol's identity, not the filename string.
    """
    raw = resources.files(SEED_RESOURCE_PACKAGE).joinpath(SEED_RESOURCE_FILENAME).read_text()
    payload = json.loads(raw)
    payload["rates"] = _flatten_utilities(payload)
    payload.pop("utilities", None)
    try:
        return UrdbSeed.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"URDB seed {SEED_RESOURCE_FILENAME!r} is malformed") from exc


def is_stale(*, snapshot_date: date, today: date, stale_after_days: int) -> bool:
    """``True`` once the snapshot is older than the configured window.

    Surfaces in the audit so users know to treat URDB-derived headline
    numbers as approximate when the rate case behind them has likely
    been superseded — URDB itself updates on a multi-week cadence.
    """
    return (today - snapshot_date) > timedelta(days=stale_after_days)


class UrdbSeedProvider:
    """``TariffProvider``-compatible adapter over the bundled seed.

    Looks up by ``(country, utility_key)`` — ZIP-level disambiguation
    isn't part of the seed, since the top-10 utilities each map to a
    well-known service territory and we'd need URDB's full territory
    polygon to do better. ZIP support lands with the live API adapter.
    """

    name: str = "urdb-seed"

    def __init__(self, seed: UrdbSeed | None = None, *, today: date | None = None) -> None:
        self._seed = seed if seed is not None else load_seed()
        self._today = today or date.today()
        self._index: dict[tuple[str, str], TariffSchedule] = {}
        for rate in self._seed.rates:
            self._index[(rate.country.upper(), rate.utility_key.upper())] = _to_schedule(rate)

    @property
    def snapshot_date(self) -> date:
        return self._seed.snapshot_date

    @property
    def stale(self) -> bool:
        return is_stale(
            snapshot_date=self._seed.snapshot_date,
            today=self._today,
            stale_after_days=self._seed.stale_warning_days,
        )

    def utilities(self) -> Iterable[str]:
        """Iterate seeded utility keys (uppercased)."""
        return (key for _country, key in self._index)

    async def fetch(self, query: TariffQuery) -> TariffSchedule:
        """Look up a schedule by ``(country, utility)``.

        The match is case-insensitive on ``utility`` so callers don't
        have to remember ``"PGE"`` vs ``"pge"``. Falls through to a
        ``LookupError`` rather than silently returning a default —
        URDB's whole point is canonical rates, so we don't want a
        misspelled utility key to quietly bind to a wrong tariff.
        """
        if query.utility is None:
            raise LookupError("UrdbSeedProvider requires a utility key in the query")
        key = (query.country.upper(), query.utility.upper())
        if key not in self._index:
            raise LookupError(
                f"URDB seed has no utility {query.utility!r} in {query.country!r}; "
                f"known: {sorted(k for _c, k in self._index)}"
            )
        return self._index[key]


__all__ = [
    "SEED_RESOURCE_FILENAME",
    "SEED_RESOURCE_PACKAGE",
    "UrdbRateSeed",
    "UrdbSeed",
    "UrdbSeedProvider",
    "is_stale",
    "load_seed",
]
