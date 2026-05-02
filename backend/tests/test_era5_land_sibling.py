"""ERA5-Land sibling adapter — NSRDB integration (chart-solar-qrhs).

Covers the parser (synthetic Open-Meteo daily payload → 12-month
aggregates) and the integration shape: ``NsrdbProvider.fetch_tmy``
merges the sibling's monthly precip + snowfall onto the PSM3 TMY, and a
sibling failure logs but doesn't break the primary fetch. The PVGIS
integration (chart-solar-p559) lives in
``test_era5_land_pvgis_sibling.py``.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import httpx
import pytest

from backend.infra.retry import reset_breakers
from backend.providers.irradiance import HOURS_PER_TMY, TmyData
from backend.providers.irradiance.era5_land import (
    Era5LandAggregates,
    Era5LandProvider,
    parse_era5_land_payload,
)
from backend.providers.irradiance.nsrdb import NsrdbProvider


@pytest.fixture(autouse=True)
def _reset_breakers() -> Iterator[None]:
    """Module-level breakers leak across tests; reset to isolate failures."""
    reset_breakers()
    yield
    reset_breakers()


def test_parse_payload_aggregates_daily_precipitation_into_months() -> None:
    """1 mm/day → Jan 31, Feb 28, Apr 30 mm in a non-leap year."""
    payload = _synthetic_daily_payload(precipitation_per_day=1.0)
    aggregates = parse_era5_land_payload(payload)

    assert aggregates.precipitation_mm_per_month is not None
    assert aggregates.precipitation_mm_per_month[0] == pytest.approx(31.0)
    assert aggregates.precipitation_mm_per_month[1] == pytest.approx(28.0)
    assert aggregates.precipitation_mm_per_month[3] == pytest.approx(30.0)


def test_parse_payload_aggregates_snowfall_into_winter_months_only() -> None:
    """Fixture: 0.5 cm/day in Jan/Feb/Dec, 0 elsewhere — matches the
    pattern the global-fallback OpenMeteo parser test pins."""
    payload = _synthetic_daily_payload(precipitation_per_day=0.0, snow_in_winter_cm=0.5)
    aggregates = parse_era5_land_payload(payload)

    assert aggregates.snowfall_cm_per_month is not None
    assert aggregates.snowfall_cm_per_month[0] == pytest.approx(15.5)  # 31 × 0.5
    assert aggregates.snowfall_cm_per_month[1] == pytest.approx(14.0)  # 28 × 0.5
    assert aggregates.snowfall_cm_per_month[5] == pytest.approx(0.0)  # Jun
    assert aggregates.snowfall_cm_per_month[11] == pytest.approx(15.5)


def test_parse_payload_returns_none_when_daily_block_missing() -> None:
    """An older / cached payload without ``daily`` keeps both fields
    ``None`` so the engine soiling/snow steps no-op gracefully."""
    aggregates = parse_era5_land_payload({"elevation": 0.0})
    assert aggregates.precipitation_mm_per_month is None
    assert aggregates.snowfall_cm_per_month is None


def test_aggregates_validate_12_length() -> None:
    """The shared aggregate type pins a 12-length array — same as
    ``TmyData``'s monthly fields."""
    with pytest.raises(ValueError):
        Era5LandAggregates(precipitation_mm_per_month=[1.0] * 11)


async def test_provider_round_trips_through_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_daily_payload(precipitation_per_day=2.0, snow_in_winter_cm=0.25)
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    _patch_async_client(monkeypatch, transport)

    provider = Era5LandProvider()
    aggregates = await provider.fetch_monthly_aggregates(40.0, -105.0)

    assert aggregates.precipitation_mm_per_month is not None
    assert aggregates.precipitation_mm_per_month[0] == pytest.approx(62.0)  # 31 × 2
    assert aggregates.snowfall_cm_per_month is not None
    assert aggregates.snowfall_cm_per_month[0] == pytest.approx(7.75)  # 31 × 0.25
    assert "archive-api.open-meteo.com" in captured["url"]


async def test_nsrdb_fetch_merges_sibling_precip_and_snow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: PSM3 fetch + sibling fetch → TmyData with all three
    monthly fields populated. Both upstreams go through MockTransport."""
    csv_text = _synthetic_nsrdb_csv(include_rh=True)
    daily_payload = _synthetic_daily_payload(precipitation_per_day=1.0)

    def handler(req: httpx.Request) -> httpx.Response:
        host = req.url.host
        if "developer.nrel.gov" in host:
            return httpx.Response(200, text=csv_text)
        if "archive-api.open-meteo.com" in host:
            return httpx.Response(200, json=daily_payload)
        raise AssertionError(f"unexpected host {host}")

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    provider = NsrdbProvider(api_key="x", user_email="x@x")
    tmy = await provider.fetch_tmy(40.0, -105.0)

    assert isinstance(tmy, TmyData)
    assert tmy.source == "nsrdb"
    # PSM3 contributions (RH from hourly).
    assert tmy.relative_humidity_pct_per_month is not None
    # Sibling contributions (precip + snow from daily archive).
    assert tmy.precipitation_mm_per_month is not None
    assert tmy.precipitation_mm_per_month[0] == pytest.approx(31.0)
    assert tmy.snowfall_cm_per_month is not None


async def test_nsrdb_fetch_continues_when_sibling_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sibling outage logs but doesn't break the audit — ``TmyData``
    comes back with the PSM3 fields and precip/snow set to ``None``."""
    csv_text = _synthetic_nsrdb_csv(include_rh=True)

    def handler(req: httpx.Request) -> httpx.Response:
        if "developer.nrel.gov" in req.url.host:
            return httpx.Response(200, text=csv_text)
        return httpx.Response(503, text="sibling boom")

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    provider = NsrdbProvider(api_key="x", user_email="x@x")
    tmy = await provider.fetch_tmy(40.0, -105.0)

    assert tmy.precipitation_mm_per_month is None
    assert tmy.snowfall_cm_per_month is None
    # PSM3 RH still populated — sibling failure didn't poison anything.
    assert tmy.relative_humidity_pct_per_month is not None


async def test_nsrdb_fetch_skips_sibling_when_sibling_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tests / future ops can pass a sibling that always returns empty
    aggregates to disable the merge entirely."""
    csv_text = _synthetic_nsrdb_csv(include_rh=True)

    def handler(req: httpx.Request) -> httpx.Response:
        if "developer.nrel.gov" in req.url.host:
            return httpx.Response(200, text=csv_text)
        raise AssertionError("sibling endpoint should not be called")

    _patch_async_client(monkeypatch, httpx.MockTransport(handler))

    class _NoOpSibling:
        async def fetch_monthly_aggregates(self, lat: float, lon: float) -> Era5LandAggregates:
            return Era5LandAggregates()

    provider = NsrdbProvider(api_key="x", user_email="x@x", sibling=_NoOpSibling())
    tmy = await provider.fetch_tmy(40.0, -105.0)
    assert tmy.precipitation_mm_per_month is None
    assert tmy.snowfall_cm_per_month is None


def _synthetic_daily_payload(
    *,
    precipitation_per_day: float,
    snow_in_winter_cm: float = 0.0,
) -> dict[str, Any]:
    """Build a 365-day non-leap daily payload — same shape as Open-Meteo's
    archive endpoint (the underlying source for the sibling adapter)."""
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


def _synthetic_nsrdb_csv(*, include_rh: bool = False) -> str:
    """Minimal valid PSM3 CSV — same shape as the existing irradiance test."""
    buf = io.StringIO()
    buf.write(
        "Source,Location ID,City,State,Country,Latitude,Longitude,Time Zone,"
        "Elevation,Local Time Zone,Dew Point Units,DHI Units,DNI Units,GHI Units,"
        "Temperature Units,Pressure Units,Wind Direction Units,Wind Speed Units\n"
    )
    buf.write("NSRDB,000000,X,X,X,40.0,-105.0,-7,1655.0,-7,c,w/m2,w/m2,w/m2,c,mbar,Degrees,m/s\n")
    base_cols = "Year,Month,Day,Hour,Minute,GHI,DNI,DHI,Temperature,Wind Speed"
    if include_rh:
        buf.write(base_cols + ",Relative Humidity\n")
    else:
        buf.write(base_cols + "\n")
    for i in range(HOURS_PER_TMY):
        ghi = max(0.0, 900.0 * (i % 24 - 12) / 12.0)
        dni = ghi * 0.85
        dhi = ghi * 0.15
        if include_rh:
            buf.write(f"2020,1,1,{i % 24},0,{ghi:.1f},{dni:.1f},{dhi:.1f},20.0,3.0,55.0\n")
        else:
            buf.write(f"2020,1,1,{i % 24},0,{ghi:.1f},{dni:.1f},{dhi:.1f},20.0,3.0\n")
    return buf.getvalue()


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    """Same seam as test_irradiance_providers — every ``AsyncClient`` gets the mock."""
    original = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
