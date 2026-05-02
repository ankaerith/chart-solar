"""ERA5-Land sibling adapter — PVGIS integration (chart-solar-p559).

Mirrors the NSRDB integration tests in ``test_era5_land_sibling``: the
same Open-Meteo-backed sibling now augments the PVGIS TMY too. UK / EU
sites get monthly precipitation + snowfall populated for the soiling
and snow engine steps.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from backend.infra.retry import reset_breakers
from backend.providers.irradiance import HOURS_PER_TMY, TmyData
from backend.providers.irradiance.era5_land import Era5LandAggregates
from backend.providers.irradiance.pvgis import PvgisProvider


@pytest.fixture(autouse=True)
def _reset_breakers() -> Iterator[None]:
    """Module-level breakers leak across tests; reset to isolate failures."""
    reset_breakers()
    yield
    reset_breakers()


async def test_pvgis_fetch_merges_sibling_precip_and_snow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: PVGIS fetch + ERA5-Land sibling fetch → TmyData
    with all monthly fields populated. Both upstreams round-trip
    through MockTransport."""
    pvgis_payload = _synthetic_pvgis_payload(include_rh=True)
    daily_payload = _synthetic_daily_payload(precipitation_per_day=2.0, snow_in_winter_cm=0.5)

    def handler(req: httpx.Request) -> httpx.Response:
        host = req.url.host
        if "jrc.ec.europa.eu" in host:
            return httpx.Response(200, json=pvgis_payload)
        if "archive-api.open-meteo.com" in host:
            return httpx.Response(200, json=daily_payload)
        raise AssertionError(f"unexpected host {host}")

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    provider = PvgisProvider()
    tmy = await provider.fetch_tmy(51.5074, -0.1278)

    assert isinstance(tmy, TmyData)
    assert tmy.source == "pvgis"
    # PVGIS contributions (RH from native column).
    assert tmy.relative_humidity_pct_per_month is not None
    # Sibling contributions (precip + snow from daily archive).
    assert tmy.precipitation_mm_per_month is not None
    assert tmy.precipitation_mm_per_month[0] == pytest.approx(62.0)  # 31 × 2
    assert tmy.snowfall_cm_per_month is not None
    assert tmy.snowfall_cm_per_month[0] == pytest.approx(15.5)  # 31 × 0.5


async def test_pvgis_fetch_continues_when_sibling_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sibling outage logs but doesn't break the audit — TmyData
    comes back with PVGIS fields populated and precip/snow ``None``."""
    pvgis_payload = _synthetic_pvgis_payload(include_rh=True)

    def handler(req: httpx.Request) -> httpx.Response:
        if "jrc.ec.europa.eu" in req.url.host:
            return httpx.Response(200, json=pvgis_payload)
        return httpx.Response(503, text="sibling boom")

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    provider = PvgisProvider()
    tmy = await provider.fetch_tmy(51.5074, -0.1278)

    assert tmy.precipitation_mm_per_month is None
    assert tmy.snowfall_cm_per_month is None
    # PVGIS RH still populated — sibling failure didn't poison anything.
    assert tmy.relative_humidity_pct_per_month is not None


async def test_pvgis_fetch_skips_sibling_when_sibling_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tests / future ops can pass a sibling that always returns empty
    aggregates to disable the merge entirely."""
    pvgis_payload = _synthetic_pvgis_payload(include_rh=True)

    def handler(req: httpx.Request) -> httpx.Response:
        if "jrc.ec.europa.eu" in req.url.host:
            return httpx.Response(200, json=pvgis_payload)
        raise AssertionError("sibling endpoint should not be called")

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    class _NoOpSibling:
        async def fetch_monthly_aggregates(self, lat: float, lon: float) -> Era5LandAggregates:
            return Era5LandAggregates()

    provider = PvgisProvider(sibling=_NoOpSibling())
    tmy = await provider.fetch_tmy(51.5074, -0.1278)
    assert tmy.precipitation_mm_per_month is None
    assert tmy.snowfall_cm_per_month is None


def _synthetic_daily_payload(
    *,
    precipitation_per_day: float,
    snow_in_winter_cm: float = 0.0,
) -> dict[str, Any]:
    """Same shape as the NSRDB sibling test fixture — Open-Meteo's
    daily archive payload, 365 non-leap days starting 2023-01-01."""
    start = date(2023, 1, 1)
    days = [(start + timedelta(days=i)) for i in range(365)]
    dates_iso = [d.isoformat() for d in days]
    snow = [snow_in_winter_cm if d.month in (1, 2, 12) else 0.0 for d in days]
    return {
        "elevation": 0.0,
        "timezone": "GMT",
        "daily": {
            "time": dates_iso,
            "precipitation_sum": [precipitation_per_day for _ in days],
            "snowfall_sum": snow,
        },
    }


def _synthetic_pvgis_payload(*, include_rh: bool = False) -> dict[str, Any]:
    """Minimal valid PVGIS response — same shape as the existing
    irradiance test fixture, trimmed to what this integration cares about."""
    rows: list[dict[str, Any]] = []
    for i in range(HOURS_PER_TMY):
        row: dict[str, Any] = {
            "time": f"20200101:{i:04d}",
            "G(h)": float(i % 1000),
            "Gb(n)": float(i % 800),
            "Gd(h)": float(i % 200),
            "T2m": 15.0,
            "WS10m": 4.0,
        }
        if include_rh:
            row["RH"] = 70.0
        rows.append(row)
    return {
        "inputs": {"location": {"elevation": 25.0}, "meteo_data": {}},
        "outputs": {"tmy_hourly": rows},
    }


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    """Same seam as the other irradiance tests."""
    original = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
