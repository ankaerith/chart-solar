"""PVGIS adapter — UK / Europe coverage (free, no API key).

Endpoint: https://re.jrc.ec.europa.eu/api/v5_2/tmy
Output:  JSON with `outputs.tmy_hourly` — 8760 records keyed by `time`,
         `G(h)` (GHI), `Gb(n)` (DNI), `Gd(h)` (DHI), `T2m`, `WS10m`.

PVGIS automatically picks the most appropriate source for the location
(SARAH2 / NSRDB / ERA5) and bakes the TMY across years 2005-2020 by
default. We trust their selection — no UI knob for it at v1.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.infra.http import make_get
from backend.providers.irradiance import HOURS_PER_TMY, IrradianceSource, TmyData

PVGIS_TMY_URL = "https://re.jrc.ec.europa.eu/api/v5_2/tmy"


class PvgisProvider:
    """JRC PVGIS TMY — Europe + Mediterranean."""

    name: IrradianceSource = "pvgis"

    def __init__(self) -> None:
        self._get = make_get(service="pvgis")

    async def fetch_tmy(self, lat: float, lon: float) -> TmyData:
        response = await self._get(
            PVGIS_TMY_URL,
            params={
                "lat": lat,
                "lon": lon,
                "outputformat": "json",
            },
        )
        return parse_pvgis_json(response.json(), source_lat=lat, source_lon=lon)


def parse_pvgis_json(
    payload: dict[str, Any],
    *,
    source_lat: float,
    source_lon: float,
) -> TmyData:
    """Parse PVGIS JSON. Pure."""
    inputs = payload.get("inputs", {})
    location = inputs.get("location", {})
    elevation = float(location.get("elevation", 0.0))
    # PVGIS doesn't return an IANA timezone — its `time` strings are
    # already in UTC. Stamping `UTC` keeps pvlib downstream consistent.
    timezone = "UTC"

    rows = payload.get("outputs", {}).get("tmy_hourly", [])
    if len(rows) != HOURS_PER_TMY:
        raise ValueError(f"PVGIS payload had {len(rows)} hourly rows; TMY must be {HOURS_PER_TMY}")

    ghi: list[float] = []
    dni: list[float] = []
    dhi: list[float] = []
    temp: list[float] = []
    wind: list[float] = []
    for row in rows:
        ghi.append(float(row["G(h)"]))
        dni.append(float(row["Gb(n)"]))
        dhi.append(float(row["Gd(h)"]))
        temp.append(float(row["T2m"]))
        wind.append(float(row["WS10m"]))

    return TmyData(
        lat=source_lat,
        lon=source_lon,
        elevation_m=elevation,
        timezone=timezone,
        source="pvgis",
        fetched_at=datetime.now(UTC),
        ghi_w_m2=ghi,
        dni_w_m2=dni,
        dhi_w_m2=dhi,
        temp_air_c=temp,
        wind_speed_m_s=wind,
    )
