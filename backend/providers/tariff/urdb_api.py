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
from datetime import datetime, timedelta
from typing import Any

import httpx

from backend.infra.http import make_get
from backend.infra.retry import CircuitOpenError, RetryExhaustedError
from backend.infra.util import utc_now
from backend.providers.tariff import (
    CurrencyCode,
    TariffQuery,
    TariffSchedule,
    TieredBlock,
    TouPeriod,
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
        clock: Callable[[], datetime] = utc_now,
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
    sector-pinned + ZIP/utility-pinned upstream). Three rate shapes are
    handled:

    * **Flat** — one period in ``energyratestructure``, one block in
      that period.
    * **Tiered** — one period, multiple blocks (``max`` boundaries).
    * **TOU** — multiple periods plus ``energyweekdayschedule`` /
      ``energyweekendschedule`` 12×24 matrices of period indices. Each
      ``(period, weekday-flag)`` pair becomes one or more
      :class:`TouPeriod` rows, grouped by months that share an
      identical hour mask so seasonal swaps survive the round-trip.

    Per-period tiered blocks (TOU-with-tiers) collapse to the first
    block's rate — the engine's TOU billing is single-rate per band.
    Multi-schedule rates (separate winter/summer documents) are out of
    scope; the seed snapshot path picks those up instead.
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

    weekday_schedule = item.get("energyweekdayschedule")
    weekend_schedule = item.get("energyweekendschedule")
    if (
        len(energy_rate_structure) > 1
        and _is_24x12_matrix(weekday_schedule)
        and _is_24x12_matrix(weekend_schedule)
    ):
        tou_periods = _build_tou_periods(
            energy_rate_structure=energy_rate_structure,
            weekday_schedule=weekday_schedule,
            weekend_schedule=weekend_schedule,
        )
        if tou_periods:
            return TariffSchedule(
                name=name,
                utility=utility,
                country=query.country,
                currency=currency,
                structure="tou",
                fixed_monthly_charge=fixed,
                tou_periods=tou_periods,
            )

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


def _is_24x12_matrix(matrix: object) -> bool:
    """URDB schedules are 12 rows × 24 cols of integer period indices."""
    if not isinstance(matrix, list) or len(matrix) != 12:
        return False
    for row in matrix:
        if not isinstance(row, list) or len(row) != 24:
            return False
    return True


def _build_tou_periods(
    *,
    energy_rate_structure: list[Any],
    weekday_schedule: list[list[int]],
    weekend_schedule: list[list[int]],
) -> list[TouPeriod]:
    """Walk URDB's period schedule into a list of :class:`TouPeriod`.

    For each ``(period_idx, is_weekday)`` pair, build a 12×24 boolean
    coverage map and group months by identical hour pattern. Months
    that share an hour mask collapse into a single ``TouPeriod`` —
    this preserves "summer 4-9 PM" / "winter 4-9 PM" as two rows when
    the patterns differ, and one row when they match.

    Periods that are referenced nowhere in the schedule (rate-card
    artefacts) drop silently; they would produce an empty hour mask
    that would fail TouPeriod's invariants.
    """
    periods: list[TouPeriod] = []
    for period_idx, blocks_raw in enumerate(energy_rate_structure):
        if not isinstance(blocks_raw, list) or not blocks_raw:
            continue
        first_block = blocks_raw[0]
        if not isinstance(first_block, dict):
            continue
        rate = float(first_block.get("rate") or 0.0)

        for is_weekday, schedule in (
            (True, weekday_schedule),
            (False, weekend_schedule),
        ):
            month_groups: dict[tuple[bool, ...], list[int]] = {}
            for month_idx, hours_row in enumerate(schedule):
                mask = tuple(int(hour_period) == period_idx for hour_period in hours_row)
                if not any(mask):
                    continue
                month_groups.setdefault(mask, []).append(month_idx + 1)

            label = f"period_{period_idx}_{'weekday' if is_weekday else 'weekend'}"
            for mask_tuple, months in month_groups.items():
                periods.append(
                    TouPeriod(
                        name=label
                        if len(month_groups) == 1
                        else f"{label}_m{months[0]:02d}-{months[-1]:02d}",
                        rate_per_kwh=rate,
                        months=months,
                        hour_mask=list(mask_tuple),
                        is_weekday=is_weekday,
                    )
                )
    return periods


__all__ = [
    "DEFAULT_CACHE_TTL",
    "URDB_API_URL",
    "UrdbApiProvider",
    "parse_urdb_response",
]
