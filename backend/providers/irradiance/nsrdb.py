"""NREL PSM3 (NSRDB) adapter — US coverage.

Endpoint: https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-tmy-download.csv
Auth:    `api_key` query param + a registered `email` query param.

PSM3 ships TMY as a CSV: two metadata header rows, then a data header,
then 8760 hourly rows (UTC offset baked in via the `Local Time Zone`
metadata). We expose the parsed shape via `TmyData`; the network layer
goes through `backend.infra.http.make_get` so retries + the per-service
breaker stay consistent with every other upstream.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from backend.infra.http import make_get
from backend.providers.irradiance import HOURS_PER_TMY, IrradianceSource, TmyData

NSRDB_PSM3_URL = "https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-tmy-download.csv"
NSRDB_ATTRIBUTES = "ghi,dni,dhi,air_temperature,wind_speed,surface_albedo,relative_humidity"


class NsrdbProvider:
    """NREL PSM3 PSU TMY for any US lat/lon."""

    name: IrradianceSource = "nsrdb"

    def __init__(self, *, api_key: str | None, user_email: str | None) -> None:
        # Stays constructable without credentials so DI wiring at app
        # startup doesn't blow up; `fetch_tmy` raises if actually called.
        self._api_key = api_key
        self._user_email = user_email
        self._get = make_get(service="nsrdb")

    async def fetch_tmy(self, lat: float, lon: float) -> TmyData:
        if not self._api_key or not self._user_email:
            raise RuntimeError(
                "NsrdbProvider requires `nsrdb_api_key` + `nsrdb_user_email` "
                "settings; register at https://developer.nrel.gov/signup/"
            )
        response = await self._get(
            NSRDB_PSM3_URL,
            params={
                "api_key": self._api_key,
                "email": self._user_email,
                "wkt": f"POINT({lon} {lat})",
                "attributes": NSRDB_ATTRIBUTES,
                "names": "tmy",
                "leap_day": "false",
                "interval": "60",
                "utc": "false",
            },
        )
        return parse_nsrdb_csv(response.text, source_lat=lat, source_lon=lon)


def parse_nsrdb_csv(body: str, *, source_lat: float, source_lon: float) -> TmyData:
    """Parse a PSM3 TMY CSV. Pure — no IO. Covered by frozen-fixture tests."""
    reader = csv.reader(io.StringIO(body))
    header_keys = next(reader)
    header_vals = next(reader)
    metadata = dict(zip(header_keys, header_vals, strict=False))

    elevation = float(metadata.get("Elevation", 0.0))
    timezone_offset_hours = float(metadata.get("Local Time Zone", 0.0))
    timezone = _offset_to_iana_etc(timezone_offset_hours)

    column_names = next(reader)
    col = {name: idx for idx, name in enumerate(column_names)}
    required = {"GHI", "DNI", "DHI", "Temperature", "Wind Speed"}
    missing = required - col.keys()
    if missing:
        raise ValueError(f"NSRDB CSV missing columns: {sorted(missing)}")

    ghi: list[float] = []
    dni: list[float] = []
    dhi: list[float] = []
    temp: list[float] = []
    wind: list[float] = []
    for row in reader:
        ghi.append(float(row[col["GHI"]]))
        dni.append(float(row[col["DNI"]]))
        dhi.append(float(row[col["DHI"]]))
        temp.append(float(row[col["Temperature"]]))
        wind.append(float(row[col["Wind Speed"]]))

    if len(ghi) != HOURS_PER_TMY:
        raise ValueError(f"NSRDB CSV had {len(ghi)} rows; TMY must be {HOURS_PER_TMY}")

    return TmyData(
        lat=source_lat,
        lon=source_lon,
        elevation_m=elevation,
        timezone=timezone,
        source="nsrdb",
        fetched_at=datetime.now(UTC),
        ghi_w_m2=ghi,
        dni_w_m2=dni,
        dhi_w_m2=dhi,
        temp_air_c=temp,
        wind_speed_m_s=wind,
    )


def _offset_to_iana_etc(offset_hours: float) -> str:
    """`Etc/GMT±N` is pvlib-friendly and uses POSIX sign convention
    (positive offset → negative `Etc/GMT-N`)."""
    sign = "-" if offset_hours > 0 else "+"
    return f"Etc/GMT{sign}{abs(int(offset_hours))}"
