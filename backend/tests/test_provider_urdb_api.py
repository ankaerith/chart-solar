"""Live URDB API adapter — recorded-fixture tests.

The seed adapter (chart-solar-i3r) ships an offline-by-default provider
the engine uses without internet. This adapter (chart-solar-67p2) hits
``api.openei.org/utility_rates`` for fresher coverage and ZIP-level
dispatch, and falls back to the seed when the API is unreachable.

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
