"""Live URDB API adapter — ``api.openei.org/utility_rates``.

The seed adapter (``backend/providers/tariff/urdb.py``) is the
offline-by-default path that satisfies dev + CI without internet.
This module is the live counterpart that hits NREL's URDB API for
fresher coverage and ZIP-level dispatch through territory polygons.

Behaviour:

* When ``urdb_api_key`` is set, we hit the live API. Responses are
  cached per ``(country, utility, zip_code)`` for ``cache_ttl`` (default
  24 h) so a single audit doesn't burn the daily key quota.
* On HTTP error, malformed payload, or missing API key, the provider
  falls back to ``UrdbSeedProvider``. The seed is the same launch-day
  contract; a network blip during an audit shouldn't break a forecast.
* ZIP-level dispatch uses URDB's address-based search — the API
  resolves the ZIP to the utility whose territory polygon covers it,
  which the seed (utility-key-only) cannot do.
* No live HTTP calls in CI: tests record a fixture payload and pass it
  through the parser. ``UrdbApiProvider.fetch`` itself is exercised
  with an httpx mock.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from backend.infra.http import make_get
from backend.infra.retry import CircuitOpenError, RetryExhaustedError
from backend.providers.tariff import (
    CurrencyCode,
    TariffQuery,
    TariffSchedule,
    TieredBlock,
)
from backend.providers.tariff.urdb import UrdbSeedProvider

URDB_API_URL = "https://api.openei.org/utility_rates"
URDB_API_VERSION = "latest"

DEFAULT_CACHE_TTL = timedelta(days=1)
DEFAULT_CACHE_MAX_ENTRIES = 1024


@dataclass(frozen=True)
class _CachedRate:
    fetched_at: datetime
    schedule: TariffSchedule


def _utc_now() -> datetime:
    return datetime.now(UTC)


class UrdbApiProvider:
    """Live URDB adapter against ``api.openei.org/utility_rates``.

    Falls back to :class:`UrdbSeedProvider` on missing key, HTTP error,
    or malformed payload. Constructable without a key — the fallback
    keeps dev + CI behaviour intact when no key is configured.
    """

    name: str = "urdb-api"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        fallback: UrdbSeedProvider | None = None,
        cache_ttl: timedelta = DEFAULT_CACHE_TTL,
        cache_max_entries: int = DEFAULT_CACHE_MAX_ENTRIES,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._api_key = api_key
        self._fallback = fallback if fallback is not None else UrdbSeedProvider()
        self._cache_ttl = cache_ttl
        self._cache_max_entries = cache_max_entries
        self._clock = clock
        # OrderedDict + LRU eviction: long-running workers can't grow
        # the cache unboundedly when each audit hits a new utility/zip.
        self._cache: OrderedDict[tuple[str, str | None, str | None], _CachedRate] = OrderedDict()
        self._get = make_get(service="urdb")

    async def fetch(self, query: TariffQuery) -> TariffSchedule:
        """Return a tariff schedule for ``query``.

        Lookup priority: cache hit → live API → seed fallback. The
        seed fallback also catches the no-API-key path so callers get
        a meaningful answer in dev without configuring credentials.
        """
        if not self._api_key:
            return await self._fallback.fetch(query)

        cache_key = (query.country.upper(), query.utility, query.zip_code)
        cached = self._cache.get(cache_key)
        now = self._clock()
        if cached is not None and (now - cached.fetched_at) < self._cache_ttl:
            self._cache.move_to_end(cache_key)
            return cached.schedule

        try:
            schedule = await self._fetch_live(query)
        except (
            httpx.HTTPError,
            RetryExhaustedError,
            CircuitOpenError,
            ValueError,
            KeyError,
        ):
            return await self._fallback.fetch(query)

        self._cache[cache_key] = _CachedRate(fetched_at=now, schedule=schedule)
        self._cache.move_to_end(cache_key)
        while len(self._cache) > self._cache_max_entries:
            self._cache.popitem(last=False)
        return schedule

    async def _fetch_live(self, query: TariffQuery) -> TariffSchedule:
        params: dict[str, Any] = {
            "api_key": self._api_key,
            "version": URDB_API_VERSION,
            "format": "json",
            "approved": "true",
            "detail": "full",
            "limit": 1,
            "sector": "Residential",
        }
        if query.zip_code:
            # URDB's address-based search resolves the ZIP to the
            # utility whose service-territory polygon covers it.
            params["address"] = query.zip_code
        if query.utility:
            params["utility"] = query.utility

        response = await self._get(URDB_API_URL, params=params)
        return parse_urdb_response(response.json(), query=query)


def parse_urdb_response(
    payload: dict[str, Any],
    *,
    query: TariffQuery,
) -> TariffSchedule:
    """Map a URDB JSON response onto :class:`TariffSchedule`.

    URDB returns ``items[]``; we take the first match (search is
    sector-pinned + ZIP/utility-pinned upstream). The energy-rate
    structure is a nested list — index 0 is the schedule the engine
    consumes; multi-schedule rates (seasonal swaps) are out of scope
    for this adapter and the seed snapshot path picks them up instead.
    """
    items = payload.get("items") or []
    if not items:
        raise ValueError("URDB response carried no items[]")
    item = items[0]

    name = item.get("name") or item.get("label") or "URDB rate"
    utility = item.get("utility") or query.utility or "unknown"
    currency: CurrencyCode = "USD"
    fixed = float(item.get("fixedchargefirstmeter") or 0.0)

    energy_rate_structure = item.get("energyratestructure") or []
    if not energy_rate_structure:
        raise ValueError(f"URDB rate {name!r} has no energyratestructure")

    blocks_raw = energy_rate_structure[0]
    if not isinstance(blocks_raw, list) or not blocks_raw:
        raise ValueError(f"URDB rate {name!r} has malformed first-period blocks")

    if len(blocks_raw) == 1:
        block = blocks_raw[0]
        return TariffSchedule(
            name=name,
            utility=utility,
            country=query.country,
            currency=currency,
            structure="flat",
            fixed_monthly_charge=fixed,
            flat_rate_per_kwh=float(block.get("rate") or 0.0),
        )

    # Multi-block first period → tiered tariff. URDB's "max" sits at
    # the top of each block (kWh boundary); the catch-all top tier has
    # no max set.
    tiered: list[TieredBlock] = []
    for block in blocks_raw:
        max_kwh = block.get("max")
        tiered.append(
            TieredBlock(
                rate_per_kwh=float(block.get("rate") or 0.0),
                up_to_kwh_per_month=float(max_kwh) if max_kwh else None,
            )
        )

    return TariffSchedule(
        name=name,
        utility=utility,
        country=query.country,
        currency=currency,
        structure="tiered",
        fixed_monthly_charge=fixed,
        tiered_blocks=tiered,
    )


__all__ = [
    "DEFAULT_CACHE_TTL",
    "URDB_API_URL",
    "UrdbApiProvider",
    "parse_urdb_response",
]
