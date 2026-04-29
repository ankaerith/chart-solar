"""Auto-router + parsers for the three irradiance providers.

The HTTP layer (`backend/infra/http.py`) is exercised indirectly via
`httpx.MockTransport` so each provider's `fetch_tmy` round-trips through
the real `make_get` retry-wrapper without any network. Parse functions
are also tested directly on synthetic payloads — that gives the cleanest
coverage for the format-specific quirks (NSRDB metadata header rows,
PVGIS leap-year handling, Open-Meteo Feb-29 trim).
"""

from __future__ import annotations

import io
from typing import Any

import httpx
import pytest

from backend.config import Settings
from backend.providers.irradiance import (
    HOURS_PER_TMY,
    TmyData,
    pick_provider,
)
from backend.providers.irradiance.nsrdb import NsrdbProvider, parse_nsrdb_csv
from backend.providers.irradiance.openmeteo import (
    OPENMETEO_FREE_URL,
    OPENMETEO_PAID_URL,
    OpenMeteoProvider,
    parse_openmeteo_json,
)
from backend.providers.irradiance.pvgis import PvgisProvider, parse_pvgis_json

# ---------------------------------------------------------------------------
# Auto-router
# ---------------------------------------------------------------------------


def test_router_us_picks_nsrdb() -> None:
    boulder = pick_provider(40.0150, -105.2705, settings=_settings(nsrdb=True))
    assert boulder.name == "nsrdb"
    assert isinstance(boulder, NsrdbProvider)


def test_router_uk_picks_pvgis() -> None:
    london = pick_provider(51.5074, -0.1278, settings=_settings())
    assert london.name == "pvgis"
    assert isinstance(london, PvgisProvider)


def test_router_global_falls_back_to_openmeteo() -> None:
    cape_town = pick_provider(-33.9249, 18.4241, settings=_settings())
    assert cape_town.name == "openmeteo"
    assert isinstance(cape_town, OpenMeteoProvider)


def test_router_alaska_and_hawaii_pick_nsrdb() -> None:
    anchorage = pick_provider(61.2181, -149.9003, settings=_settings(nsrdb=True))
    honolulu = pick_provider(21.3099, -157.8581, settings=_settings(nsrdb=True))
    assert anchorage.name == "nsrdb"
    assert honolulu.name == "nsrdb"


def test_router_eu_european_locations_pick_pvgis() -> None:
    paris = pick_provider(48.8566, 2.3522, settings=_settings())
    rome = pick_provider(41.9028, 12.4964, settings=_settings())
    assert paris.name == "pvgis"
    assert rome.name == "pvgis"


# ---------------------------------------------------------------------------
# NSRDB parser
# ---------------------------------------------------------------------------


def test_parse_nsrdb_csv_returns_8760_hour_tmy() -> None:
    csv_text = _synthetic_nsrdb_csv(hours=HOURS_PER_TMY, elevation=1655.0)
    tmy = parse_nsrdb_csv(csv_text, source_lat=40.0150, source_lon=-105.2705)

    assert tmy.source == "nsrdb"
    assert tmy.lat == pytest.approx(40.0150)
    assert tmy.elevation_m == pytest.approx(1655.0)
    assert len(tmy.ghi_w_m2) == HOURS_PER_TMY
    assert len(tmy.dni_w_m2) == HOURS_PER_TMY
    assert len(tmy.dhi_w_m2) == HOURS_PER_TMY
    assert len(tmy.temp_air_c) == HOURS_PER_TMY
    assert len(tmy.wind_speed_m_s) == HOURS_PER_TMY


def test_parse_nsrdb_csv_rejects_truncated() -> None:
    csv_text = _synthetic_nsrdb_csv(hours=24, elevation=0)
    with pytest.raises(ValueError, match="must be 8760"):
        parse_nsrdb_csv(csv_text, source_lat=0.0, source_lon=0.0)


def test_parse_nsrdb_csv_rejects_missing_columns() -> None:
    bad = "Elevation,Local Time Zone\n0,-7\nMonth,Day,Hour\n1,1,0\n"
    with pytest.raises(ValueError, match="missing columns"):
        parse_nsrdb_csv(bad, source_lat=0.0, source_lon=0.0)


def test_nsrdb_provider_raises_without_credentials() -> None:
    p = NsrdbProvider(api_key=None, user_email=None)
    with pytest.raises(RuntimeError, match="nsrdb_api_key"):

        async def run() -> None:
            await p.fetch_tmy(40.0, -105.0)

        import asyncio

        asyncio.run(run())


# ---------------------------------------------------------------------------
# PVGIS parser
# ---------------------------------------------------------------------------


def test_parse_pvgis_json_returns_8760_hour_tmy() -> None:
    payload = _synthetic_pvgis_payload(hours=HOURS_PER_TMY, elevation=15.0)
    tmy = parse_pvgis_json(payload, source_lat=51.5074, source_lon=-0.1278)

    assert tmy.source == "pvgis"
    assert tmy.elevation_m == pytest.approx(15.0)
    assert tmy.timezone == "UTC"
    assert len(tmy.ghi_w_m2) == HOURS_PER_TMY


def test_parse_pvgis_json_rejects_short_payload() -> None:
    payload = _synthetic_pvgis_payload(hours=24, elevation=0.0)
    with pytest.raises(ValueError, match="must be 8760"):
        parse_pvgis_json(payload, source_lat=0.0, source_lon=0.0)


# ---------------------------------------------------------------------------
# Open-Meteo parser + paid-flag plumbing
# ---------------------------------------------------------------------------


def test_parse_openmeteo_json_8760() -> None:
    payload = _synthetic_openmeteo_payload(hours=HOURS_PER_TMY, elevation=42.0)
    tmy = parse_openmeteo_json(payload, source_lat=-33.9249, source_lon=18.4241)
    assert tmy.source == "openmeteo"
    assert len(tmy.ghi_w_m2) == HOURS_PER_TMY


def test_parse_openmeteo_json_drops_feb29_in_leap_year() -> None:
    payload = _synthetic_openmeteo_payload(hours=8784, elevation=0.0)
    tmy = parse_openmeteo_json(payload, source_lat=0.0, source_lon=0.0)
    assert len(tmy.ghi_w_m2) == HOURS_PER_TMY


def test_openmeteo_provider_uses_free_endpoint_by_default() -> None:
    p = OpenMeteoProvider()
    assert p.endpoint == OPENMETEO_FREE_URL


def test_openmeteo_provider_uses_paid_endpoint_when_flagged() -> None:
    p = OpenMeteoProvider(paid_enabled=True, api_key="test-key")
    assert p.endpoint == OPENMETEO_PAID_URL


async def test_openmeteo_paid_without_key_raises() -> None:
    p = OpenMeteoProvider(paid_enabled=True, api_key=None)
    with pytest.raises(RuntimeError, match="openmeteo_paid_api_key"):
        await p.fetch_tmy(0.0, 0.0)


# ---------------------------------------------------------------------------
# End-to-end via httpx.MockTransport — provider.fetch_tmy() round-trip
# ---------------------------------------------------------------------------


async def test_pvgis_fetch_round_trips_through_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_pvgis_payload(hours=HOURS_PER_TMY, elevation=25.0)
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=payload),
    )
    _patch_async_client(monkeypatch, transport)

    p = PvgisProvider()
    tmy = await p.fetch_tmy(51.5074, -0.1278)
    assert isinstance(tmy, TmyData)
    assert tmy.source == "pvgis"
    assert len(tmy.ghi_w_m2) == HOURS_PER_TMY


async def test_openmeteo_fetch_round_trips_through_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _synthetic_openmeteo_payload(hours=HOURS_PER_TMY, elevation=10.0)
    captured: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        captured["url"] = str(req.url)
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    _patch_async_client(monkeypatch, transport)

    p = OpenMeteoProvider()
    tmy = await p.fetch_tmy(-33.9249, 18.4241)

    assert tmy.source == "openmeteo"
    assert len(tmy.ghi_w_m2) == HOURS_PER_TMY
    assert OPENMETEO_FREE_URL.split("//", 1)[1].split("/", 1)[0] in captured["url"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(nsrdb: bool = False, openmeteo_paid: bool = False) -> Settings:
    s = Settings()
    if nsrdb:
        s = s.model_copy(update={"nsrdb_api_key": "x", "nsrdb_user_email": "x@x"})
    if openmeteo_paid:
        s = s.model_copy(update={"openmeteo_paid_enabled": True, "openmeteo_paid_api_key": "y"})
    return s


def _synthetic_nsrdb_csv(*, hours: int, elevation: float) -> str:
    """PSM3 CSV: 2 metadata header rows + data header + `hours` data rows."""
    buf = io.StringIO()
    writer_meta = io.StringIO()
    writer_meta.write(
        "Source,Location ID,City,State,Country,Latitude,Longitude,Time Zone,"
        "Elevation,Local Time Zone,Dew Point Units,DHI Units,DNI Units,GHI Units,"
        "Temperature Units,Pressure Units,Wind Direction Units,Wind Speed Units\n"
    )
    writer_meta.write(
        f"NSRDB,000000,X,X,X,40.0,-105.0,-7,{elevation},-7,c,w/m2,w/m2,w/m2,c,mbar,Degrees,m/s\n"
    )
    buf.write(writer_meta.getvalue())
    buf.write("Year,Month,Day,Hour,Minute,GHI,DNI,DHI,Temperature,Wind Speed\n")
    for i in range(hours):
        # Trivial diurnal sine: peak GHI 900 W/m², no negatives.
        ghi = max(0.0, 900.0 * (i % 24 - 12) / 12.0)
        dni = ghi * 0.85
        dhi = ghi * 0.15
        buf.write(f"2020,1,1,{i % 24},0,{ghi:.1f},{dni:.1f},{dhi:.1f},20.0,3.0\n")
    return buf.getvalue()


def _synthetic_pvgis_payload(*, hours: int, elevation: float) -> dict[str, Any]:
    rows = [
        {
            "time": f"2020{m:02d}{d:02d}:{h:02d}00",
            "G(h)": float(i % 1000),
            "Gb(n)": float(i % 800),
            "Gd(h)": float(i % 200),
            "T2m": 15.0,
            "WS10m": 4.0,
        }
        for i, (m, d, h) in enumerate(_iter_hours(hours))
    ]
    return {
        "inputs": {
            "location": {"elevation": elevation},
            "meteo_data": {},
        },
        "outputs": {"tmy_hourly": rows},
    }


def _synthetic_openmeteo_payload(*, hours: int, elevation: float) -> dict[str, Any]:
    return {
        "elevation": elevation,
        "timezone": "GMT",
        "hourly": {
            "shortwave_radiation": [float(i % 900) for i in range(hours)],
            "direct_normal_irradiance": [float(i % 700) for i in range(hours)],
            "diffuse_radiation": [float(i % 200) for i in range(hours)],
            "temperature_2m": [10.0 for _ in range(hours)],
            "wind_speed_10m": [3.0 for _ in range(hours)],
        },
    }


def _iter_hours(total: int) -> list[tuple[int, int, int]]:
    """Generate (month, day, hour) tuples without caring whether they're
    real calendar dates — the parser only reads numeric fields."""
    out: list[tuple[int, int, int]] = []
    for i in range(total):
        out.append((1, 1 + (i // 24) % 28, i % 24))
    return out


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    """Wrap `httpx.AsyncClient` so every instantiation gets a MockTransport.

    `make_get` constructs `AsyncClient` per-call, so transport injection
    via init is the cleanest test seam — no need to monkeypatch every
    provider's `_get`.
    """
    original = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)
