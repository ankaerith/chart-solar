"""Live URDB API adapter — recorded-fixture tests.

The seed adapter ships an offline-by-default provider the engine uses
without internet. The live adapter hits ``api.openei.org/utility_rates``
for fresher coverage and ZIP-level dispatch, and falls back to the
seed when the API is unreachable.

CI runs zero live calls — every test pins the URDB JSON via an
``httpx.MockTransport`` or feeds the parser directly.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest

from backend.infra.retry import reset_breakers
from backend.providers.tariff import TariffQuery, TariffSchedule
from backend.providers.tariff.urdb import UrdbSeedProvider
from backend.providers.tariff.urdb_api import (
    URDB_API_URL,
    UrdbApiProvider,
    parse_urdb_response,
)


@pytest.fixture(autouse=True)
def _reset_circuit_breakers() -> Iterator[None]:
    """Each test starts with a clean breaker — the 503-fallback test
    trips the urdb circuit after 4 attempts, and that state would
    otherwise leak into the cache + happy-path tests."""
    reset_breakers()
    yield
    reset_breakers()


# Recorded URDB-shaped payloads ---------------------------------------


def _flat_rate_payload() -> dict[str, Any]:
    """Single-block rate → flat tariff."""
    return {
        "items": [
            {
                "label": "abc123",
                "name": "Residential Service",
                "utility": "Test Utility",
                "fixedchargefirstmeter": 12.50,
                "energyratestructure": [[{"rate": 0.135}]],
            }
        ]
    }


def _tiered_rate_payload() -> dict[str, Any]:
    """Multi-block rate with `max` boundaries → tiered tariff."""
    return {
        "items": [
            {
                "label": "def456",
                "name": "Tier 1/2 Residential",
                "utility": "Tiered Utility",
                "fixedchargefirstmeter": 8.0,
                "energyratestructure": [
                    [
                        {"rate": 0.10, "max": 500.0},
                        {"rate": 0.18},  # catch-all top tier
                    ]
                ],
            }
        ]
    }


def _empty_payload() -> dict[str, Any]:
    return {"items": []}


def _tou_year_round_payload() -> dict[str, Any]:
    """Two-period TOU with the same hour pattern across all 12 months.

    Period 0 covers off-peak hours (everything except 4-9 PM); period
    1 covers peak (4-9 PM). Weekend schedule is all off-peak so peak
    only applies Mon-Fri. This is the simplest TOU shape that exercises
    the year-round month-grouping path.
    """
    weekday = []
    for _month in range(12):
        row = [0] * 24
        for hour in range(16, 21):  # 4-9 PM peak
            row[hour] = 1
        weekday.append(row)
    weekend = [[0] * 24 for _ in range(12)]
    return {
        "items": [
            {
                "label": "tou-yr",
                "name": "TOU-A",
                "utility": "TOU Utility",
                "fixedchargefirstmeter": 10.0,
                "energyratestructure": [
                    [{"rate": 0.10}],  # period 0: off-peak
                    [{"rate": 0.45}],  # period 1: peak
                ],
                "energyweekdayschedule": weekday,
                "energyweekendschedule": weekend,
            }
        ]
    }


def _tou_seasonal_payload() -> dict[str, Any]:
    """TOU with summer (Jun-Sep) peak hours different from winter peak.

    Summer peak: 1-7 PM. Winter peak: 5-9 PM. Off-peak fills the rest.
    Two distinct hour masks for period 1 → two TouPeriod rows on the
    weekday side.
    """
    weekday: list[list[int]] = []
    for month_idx in range(12):
        row = [0] * 24
        if 5 <= month_idx <= 8:  # Jun(5)-Sep(8)
            for hour in range(13, 19):
                row[hour] = 1
        else:
            for hour in range(17, 21):
                row[hour] = 1
        weekday.append(row)
    weekend = [[0] * 24 for _ in range(12)]
    return {
        "items": [
            {
                "label": "tou-seasonal",
                "name": "TOU-Seasonal",
                "utility": "Seasonal Utility",
                "fixedchargefirstmeter": 5.0,
                "energyratestructure": [
                    [{"rate": 0.12}],
                    [{"rate": 0.50}],
                ],
                "energyweekdayschedule": weekday,
                "energyweekendschedule": weekend,
            }
        ]
    }


# Parser tests --------------------------------------------------------


def test_parse_flat_rate_produces_flat_schedule() -> None:
    sched = parse_urdb_response(
        _flat_rate_payload(),
        query=TariffQuery(country="US", utility="Test Utility"),
    )
    assert isinstance(sched, TariffSchedule)
    assert sched.structure == "flat"
    assert sched.flat_rate_per_kwh == pytest.approx(0.135)
    assert sched.fixed_monthly_charge == pytest.approx(12.50)
    assert sched.utility == "Test Utility"


def test_parse_tiered_rate_produces_tiered_schedule_with_open_top_tier() -> None:
    sched = parse_urdb_response(
        _tiered_rate_payload(),
        query=TariffQuery(country="US"),
    )
    assert sched.structure == "tiered"
    assert sched.tiered_blocks is not None
    assert len(sched.tiered_blocks) == 2
    # First tier: 0–500 kWh at $0.10
    assert sched.tiered_blocks[0].rate_per_kwh == pytest.approx(0.10)
    assert sched.tiered_blocks[0].up_to_kwh_per_month == pytest.approx(500.0)
    # Top tier: open (catch-all)
    assert sched.tiered_blocks[1].up_to_kwh_per_month is None


def test_parse_empty_payload_raises() -> None:
    with pytest.raises(ValueError, match="no items"):
        parse_urdb_response(_empty_payload(), query=TariffQuery())


def test_parse_payload_with_empty_energyratestructure_raises() -> None:
    payload = {"items": [{"name": "Bad rate", "utility": "U", "energyratestructure": []}]}
    with pytest.raises(ValueError, match="no energyratestructure"):
        parse_urdb_response(payload, query=TariffQuery())


def test_parse_year_round_tou_collapses_months_into_one_period_per_band() -> None:
    """Same hour mask Jan..Dec → one weekday row per period (off-peak +
    peak) covering all 12 months. Weekend schedule is all off-peak →
    one weekend row covering off-peak only."""
    sched = parse_urdb_response(
        _tou_year_round_payload(),
        query=TariffQuery(country="US", utility="TOU Utility"),
    )
    assert sched.structure == "tou"
    assert sched.tou_periods is not None

    weekday_rows = [p for p in sched.tou_periods if p.is_weekday]
    weekend_rows = [p for p in sched.tou_periods if not p.is_weekday]
    assert len(weekday_rows) == 2
    assert len(weekend_rows) == 1

    # Each weekday row should span all 12 months (one mask, one group).
    for row in weekday_rows:
        assert sorted(row.months) == list(range(1, 13))

    peak = next(p for p in weekday_rows if p.rate_per_kwh == pytest.approx(0.45))
    off = next(p for p in weekday_rows if p.rate_per_kwh == pytest.approx(0.10))
    assert peak.hour_mask[16:21] == [True] * 5
    assert sum(peak.hour_mask) == 5
    assert off.hour_mask[12] is True  # noon is off-peak
    assert off.hour_mask[17] is False  # 5 PM is peak, not off-peak

    # Weekend off-peak covers all 24 hours, all 12 months.
    weekend_off = weekend_rows[0]
    assert sorted(weekend_off.months) == list(range(1, 13))
    assert all(weekend_off.hour_mask)


def test_parse_seasonal_tou_groups_summer_and_winter_separately() -> None:
    """Summer (Jun-Sep) and winter peak windows differ → period 1
    splits into two weekday rows, one per season. Period 0 likewise
    splits because off-peak hours are the inverse of peak."""
    sched = parse_urdb_response(
        _tou_seasonal_payload(),
        query=TariffQuery(country="US", utility="Seasonal Utility"),
    )
    assert sched.structure == "tou"
    assert sched.tou_periods is not None

    peak_rows = [p for p in sched.tou_periods if p.is_weekday and p.rate_per_kwh == 0.50]
    assert len(peak_rows) == 2
    summer_peak = next(p for p in peak_rows if 6 in p.months)
    winter_peak = next(p for p in peak_rows if 1 in p.months)

    assert sorted(summer_peak.months) == [6, 7, 8, 9]
    assert summer_peak.hour_mask[13:19] == [True] * 6
    assert sum(summer_peak.hour_mask) == 6

    assert sorted(winter_peak.months) == [1, 2, 3, 4, 5, 10, 11, 12]
    assert winter_peak.hour_mask[17:21] == [True] * 4
    assert sum(winter_peak.hour_mask) == 4


def test_parse_tou_falls_back_to_flat_when_schedule_matrix_malformed() -> None:
    """Multi-period rate without proper 12×24 schedules → drop into
    the flat/tiered path instead of producing an empty TOU schedule."""
    payload = {
        "items": [
            {
                "name": "Mis-shaped TOU",
                "utility": "U",
                "energyratestructure": [
                    [{"rate": 0.10}],
                    [{"rate": 0.45}],
                ],
                "energyweekdayschedule": [[0] * 24],  # only 1 row, not 12
                "energyweekendschedule": [[0] * 24] * 12,
            }
        ]
    }
    sched = parse_urdb_response(payload, query=TariffQuery())
    assert sched.structure == "flat"
    assert sched.flat_rate_per_kwh == pytest.approx(0.10)


# Provider behaviour: cache, fallback, no-key path --------------------


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    original = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


async def test_provider_falls_back_to_seed_when_api_key_is_missing() -> None:
    """No key → seed provider answers immediately, no HTTP call attempted."""
    seed = UrdbSeedProvider()
    provider = UrdbApiProvider(api_key=None, fallback=seed)

    # PGE is in the seed; the seed's lookup is by utility_key (uppercased).
    sched = await provider.fetch(TariffQuery(country="US", utility="PGE"))
    assert sched.utility  # non-empty proves the seed answered


async def test_provider_falls_back_to_seed_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """5xx response → fallback path, no exception escapes."""
    transport = httpx.MockTransport(lambda req: httpx.Response(503))
    _patch_async_client(monkeypatch, transport)

    provider = UrdbApiProvider(api_key="test-key")
    sched = await provider.fetch(TariffQuery(country="US", utility="PGE"))
    assert sched is not None  # seed answered after the API blew up


async def test_provider_falls_back_to_seed_on_empty_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """200 with empty items[] → parser raises → fallback path."""
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=_empty_payload()))
    _patch_async_client(monkeypatch, transport)

    provider = UrdbApiProvider(api_key="test-key")
    sched = await provider.fetch(TariffQuery(country="US", utility="PGE"))
    assert sched is not None


async def test_provider_returns_live_payload_when_api_responds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: live JSON parses straight through. The captured URL
    proves we hit the live endpoint, not the seed."""
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(200, json=_flat_rate_payload())

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    provider = UrdbApiProvider(api_key="test-key")
    sched = await provider.fetch(
        TariffQuery(country="US", utility="Test Utility", zip_code="94102")
    )
    assert URDB_API_URL.split("//", 1)[1].split("/", 1)[0] in captured["url"]
    assert "address=94102" in captured["url"]
    assert sched.flat_rate_per_kwh == pytest.approx(0.135)


async def test_provider_caches_within_ttl(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second call inside the TTL window must not hit the network."""
    call_count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_flat_rate_payload())

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    provider = UrdbApiProvider(api_key="k", cache_ttl=timedelta(hours=24))
    query = TariffQuery(country="US", utility="Test Utility", zip_code="94102")

    await provider.fetch(query)
    await provider.fetch(query)
    assert call_count["n"] == 1


async def test_provider_refetches_after_ttl_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After the TTL window elapses, the next call hits the network again."""
    call_count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_flat_rate_payload())

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    fake_now = [datetime(2026, 5, 1, tzinfo=UTC)]

    def clock() -> datetime:
        return fake_now[0]

    provider = UrdbApiProvider(
        api_key="k",
        cache_ttl=timedelta(hours=1),
        clock=clock,
    )
    query = TariffQuery(country="US", utility="U", zip_code="94102")

    await provider.fetch(query)
    fake_now[0] = fake_now[0] + timedelta(hours=2)
    await provider.fetch(query)
    assert call_count["n"] == 2


async def test_provider_keys_cache_per_utility_zip_country(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Different ZIP / utility / country should not share a cache slot."""
    call_count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_flat_rate_payload())

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    provider = UrdbApiProvider(api_key="k")
    await provider.fetch(TariffQuery(country="US", utility="A", zip_code="94102"))
    await provider.fetch(TariffQuery(country="US", utility="A", zip_code="10001"))
    await provider.fetch(TariffQuery(country="US", utility="B", zip_code="94102"))
    assert call_count["n"] == 3


async def test_provider_evicts_lru_when_cache_exceeds_max(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LRU eviction caps cache memory in long-running workers. After
    filling beyond cache_max_entries, the oldest entry is dropped and
    re-querying it triggers a refetch."""
    call_count = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(200, json=_flat_rate_payload())

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    provider = UrdbApiProvider(api_key="k", cache_max_entries=2)
    a = TariffQuery(country="US", utility="A", zip_code="94102")
    b = TariffQuery(country="US", utility="B", zip_code="94102")
    c = TariffQuery(country="US", utility="C", zip_code="94102")

    await provider.fetch(a)  # cache = [a]
    await provider.fetch(b)  # cache = [a, b]
    await provider.fetch(c)  # cache = [b, c] — a evicted (oldest)
    await provider.fetch(b)  # cache hit, no network
    await provider.fetch(a)  # refetch — a was evicted

    assert call_count["n"] == 4  # a, b, c, a-refetch
    assert len(provider._cache) == 2
