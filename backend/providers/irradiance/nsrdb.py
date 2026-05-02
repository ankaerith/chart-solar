"""NREL NSRDB GOES TMY (PSM v4) adapter — US coverage.

Endpoint: https://developer.nlr.gov/api/nsrdb/v2/solar/nsrdb-GOES-tmy-v4-0-0-download.csv
Auth:    `api_key` query param + a registered `email` query param.

NREL migrated the developer host from ``developer.nrel.gov`` to
``developer.nlr.gov`` and superseded PSM v3 with GOES TMY v4 in early
2026. The .csv synchronous mode is constrained to single-POINT,
single-YEAR requests — that's exactly our access pattern. The
alternative .json mode is async (email-link), which doesn't fit a
60s worker timeout.

The CSV shape is unchanged from v3: two metadata header rows, then a
data header, then 8760 hourly rows (UTC offset baked in via the
``Local Time Zone`` metadata). We expose the parsed shape via
``TmyData``; the network layer goes through
``backend.infra.http.make_get`` so retries + the per-service breaker
stay consistent with every other upstream.

Monthly aggregates: PSM3 carries hourly Relative Humidity, which we
average into ``relative_humidity_pct_per_month`` so the soiling step
can run on US sites without a sibling provider call. PSM3 does *not*
carry surface precipitation or snowfall — those come from the
``era5_land`` sibling adapter (chart-solar-qrhs) which the constructor
accepts as a DI seam. The primary fetch and the sibling fetch run
concurrently; sibling failure logs but doesn't break the audit.
"""

from __future__ import annotations

import csv
import io

from backend.infra.http import make_get
from backend.infra.util import utc_now
from backend.providers.irradiance import HOURS_PER_TMY, IrradianceSource, TmyData
from backend.providers.irradiance._aggregation import aggregate_hourly_to_monthly_mean
from backend.providers.irradiance.era5_land import (
    Era5LandProvider,
    Era5LandSibling,
    fetch_aggregates_with_primary,
)

NSRDB_PSM3_URL = "https://developer.nlr.gov/api/nsrdb/v2/solar/nsrdb-GOES-tmy-v4-0-0-download.csv"
NSRDB_ATTRIBUTES = "ghi,dni,dhi,air_temperature,wind_speed,surface_albedo,relative_humidity"


class NsrdbProvider:
    """NREL PSM3 PSU TMY for any US lat/lon."""

    name: IrradianceSource = "nsrdb"

    def __init__(
        self,
        *,
        api_key: str | None,
        user_email: str | None,
        sibling: Era5LandSibling | None = None,
    ) -> None:
        # Stays constructable without credentials so DI wiring at app
        # startup doesn't blow up; `fetch_tmy` raises if actually called.
        self._api_key = api_key
        self._user_email = user_email
        self._get = make_get(service="nsrdb")
        self._sibling: Era5LandSibling = sibling if sibling is not None else Era5LandProvider()

    async def fetch_tmy(self, lat: float, lon: float) -> TmyData:
        if not self._api_key or not self._user_email:
            raise RuntimeError(
                "NsrdbProvider requires `nsrdb_api_key` + `nsrdb_user_email` "
                "settings; register at https://developer.nlr.gov/signup/"
            )
        return await fetch_aggregates_with_primary(
            self._sibling,
            self._fetch_psm3(lat, lon),
            lat=lat,
            lon=lon,
        )

    async def _fetch_psm3(self, lat: float, lon: float) -> TmyData:
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
    rh_idx = col.get("Relative Humidity")

    ghi: list[float] = []
    dni: list[float] = []
    dhi: list[float] = []
    temp: list[float] = []
    wind: list[float] = []
    rh: list[float] = []
    for row in reader:
        ghi.append(float(row[col["GHI"]]))
        dni.append(float(row[col["DNI"]]))
        dhi.append(float(row[col["DHI"]]))
        temp.append(float(row[col["Temperature"]]))
        wind.append(float(row[col["Wind Speed"]]))
        if rh_idx is not None:
            rh.append(float(row[rh_idx]))

    if len(ghi) != HOURS_PER_TMY:
        raise ValueError(f"NSRDB CSV had {len(ghi)} rows; TMY must be {HOURS_PER_TMY}")

    monthly_rh: list[float] | None = None
    if rh_idx is not None and len(rh) == HOURS_PER_TMY:
        monthly_rh = aggregate_hourly_to_monthly_mean(rh)

    return TmyData(
        lat=source_lat,
        lon=source_lon,
        elevation_m=elevation,
        timezone=timezone,
        source="nsrdb",
        fetched_at=utc_now(),
        ghi_w_m2=ghi,
        dni_w_m2=dni,
        dhi_w_m2=dhi,
        temp_air_c=temp,
        wind_speed_m_s=wind,
        relative_humidity_pct_per_month=monthly_rh,
    )


def _offset_to_iana_etc(offset_hours: float) -> str:
    """`Etc/GMT±N` is pvlib-friendly and uses POSIX sign convention
    (positive offset → negative `Etc/GMT-N`)."""
    sign = "-" if offset_hours > 0 else "+"
    return f"Etc/GMT{sign}{abs(int(offset_hours))}"
