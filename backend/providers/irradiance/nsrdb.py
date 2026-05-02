"""NREL PSM3 (NSRDB) adapter — US coverage.

Endpoint: https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-tmy-download.csv
Auth:    `api_key` query param + a registered `email` query param.

PSM3 ships TMY as a CSV: two metadata header rows, then a data header,
then 8760 hourly rows (UTC offset baked in via the `Local Time Zone`
metadata). We expose the parsed shape via `TmyData`; the network layer
goes through `backend.infra.http.make_get` so retries + the per-service
breaker stay consistent with every other upstream.

Monthly aggregates: PSM3 carries hourly Relative Humidity, which we
average into ``relative_humidity_pct_per_month`` so the soiling step
can run on US sites without a sibling provider call. PSM3 does *not*
carry surface precipitation or snowfall — those come from the
``era5_land`` sibling adapter (chart-solar-qrhs), which the
constructor accepts as a DI seam. ``Era5LandProvider`` is the default;
pass a sibling that returns empty aggregates to skip the merge — both
fields stay ``None`` and the engine soiling / snow steps no-op the same
way they did before the sibling existed.
"""

from __future__ import annotations

import csv
import io
import logging

from backend.infra.http import make_get
from backend.infra.util import utc_now
from backend.providers.irradiance import HOURS_PER_TMY, IrradianceSource, TmyData
from backend.providers.irradiance._aggregation import aggregate_hourly_to_monthly_mean
from backend.providers.irradiance.era5_land import Era5LandProvider

NSRDB_PSM3_URL = "https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-tmy-download.csv"
NSRDB_ATTRIBUTES = "ghi,dni,dhi,air_temperature,wind_speed,surface_albedo,relative_humidity"

_logger = logging.getLogger(__name__)


class NsrdbProvider:
    """NREL PSM3 PSU TMY for any US lat/lon."""

    name: IrradianceSource = "nsrdb"

    def __init__(
        self,
        *,
        api_key: str | None,
        user_email: str | None,
        sibling: Era5LandProvider | None = None,
    ) -> None:
        # Stays constructable without credentials so DI wiring at app
        # startup doesn't blow up; `fetch_tmy` raises if actually called.
        self._api_key = api_key
        self._user_email = user_email
        self._get = make_get(service="nsrdb")
        # ``sibling`` is omitted only by tests that want to verify the
        # PSM3-only path; production wiring always uses the default.
        self._sibling = sibling if sibling is not None else Era5LandProvider()

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
        tmy = parse_nsrdb_csv(response.text, source_lat=lat, source_lon=lon)
        return await self._merge_sibling(tmy, lat=lat, lon=lon)

    async def _merge_sibling(self, tmy: TmyData, *, lat: float, lon: float) -> TmyData:
        """Augment the PSM3 TMY with the ERA5-Land sibling's monthly
        precipitation + snowfall, if the sibling responds.

        A sibling failure must not break the primary fetch — the
        homeowner's audit doesn't depend on snow/precip — so on any
        exception we log and return ``tmy`` unchanged. The engine's
        soiling / snow steps already no-op when those fields are unset.
        """
        try:
            agg = await self._sibling.fetch_monthly_aggregates(lat, lon)
        except Exception:
            _logger.warning(
                "era5_land sibling fetch failed at (%.4f, %.4f); "
                "leaving precip + snow fields unset",
                lat,
                lon,
                exc_info=True,
            )
            return tmy
        return tmy.model_copy(
            update={
                "precipitation_mm_per_month": agg.precipitation_mm_per_month,
                "snowfall_cm_per_month": agg.snowfall_cm_per_month,
            }
        )


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
