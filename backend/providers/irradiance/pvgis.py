"""PVGIS adapter — UK / Europe coverage (free, no API key).

Endpoint: https://re.jrc.ec.europa.eu/api/v5_2/tmy
Output:  JSON with `outputs.tmy_hourly` — 8760 records keyed by `time`,
         `G(h)` (GHI), `Gb(n)` (DNI), `Gd(h)` (DHI), `T2m`, `WS10m`,
         and `RH` (relative humidity, %).

PVGIS automatically picks the most appropriate source for the location
(SARAH2 / NSRDB / ERA5) and bakes the TMY across years 2005-2020 by
default. We trust their selection — no UI knob for it at v1.

Monthly aggregates: PVGIS's `RH` column populates
``relative_humidity_pct_per_month`` so the HSU soiling step runs on
UK/EU sites without a sibling provider call. PVGIS does *not* carry
surface precipitation or snowfall — those come from the ``era5_land``
sibling adapter (chart-solar-p559), which the constructor accepts as a
DI seam. ``Era5LandProvider`` is the default; a sibling failure logs
but doesn't break the audit (the engine snow / soiling-precip paths
already no-op when the monthly fields are unset).
"""

from __future__ import annotations

import logging
from typing import Any

from backend.infra.http import make_get
from backend.infra.util import utc_now
from backend.providers.irradiance import HOURS_PER_TMY, IrradianceSource, TmyData
from backend.providers.irradiance._aggregation import aggregate_hourly_to_monthly_mean
from backend.providers.irradiance.era5_land import Era5LandProvider

PVGIS_TMY_URL = "https://re.jrc.ec.europa.eu/api/v5_2/tmy"

_logger = logging.getLogger(__name__)


class PvgisProvider:
    """JRC PVGIS TMY — Europe + Mediterranean."""

    name: IrradianceSource = "pvgis"

    def __init__(self, *, sibling: Era5LandProvider | None = None) -> None:
        self._get = make_get(service="pvgis")
        # ``sibling`` is omitted only by tests that want to verify the
        # PVGIS-only path; production wiring always uses the default.
        self._sibling = sibling if sibling is not None else Era5LandProvider()

    async def fetch_tmy(self, lat: float, lon: float) -> TmyData:
        response = await self._get(
            PVGIS_TMY_URL,
            params={
                "lat": lat,
                "lon": lon,
                "outputformat": "json",
            },
        )
        tmy = parse_pvgis_json(response.json(), source_lat=lat, source_lon=lon)
        return await self._merge_sibling(tmy, lat=lat, lon=lon)

    async def _merge_sibling(self, tmy: TmyData, *, lat: float, lon: float) -> TmyData:
        """Augment the PVGIS TMY with the ERA5-Land sibling's monthly
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
    rh: list[float] = []
    has_rh = bool(rows) and "RH" in rows[0]
    for row in rows:
        ghi.append(float(row["G(h)"]))
        dni.append(float(row["Gb(n)"]))
        dhi.append(float(row["Gd(h)"]))
        temp.append(float(row["T2m"]))
        wind.append(float(row["WS10m"]))
        if has_rh:
            rh.append(float(row["RH"]))

    monthly_rh: list[float] | None = None
    if has_rh and len(rh) == HOURS_PER_TMY:
        monthly_rh = aggregate_hourly_to_monthly_mean(rh)

    return TmyData(
        lat=source_lat,
        lon=source_lon,
        elevation_m=elevation,
        timezone=timezone,
        source="pvgis",
        fetched_at=utc_now(),
        ghi_w_m2=ghi,
        dni_w_m2=dni,
        dhi_w_m2=dhi,
        temp_air_c=temp,
        wind_speed_m_s=wind,
        relative_humidity_pct_per_month=monthly_rh,
    )
