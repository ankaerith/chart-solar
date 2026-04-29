"""Deterministic synthetic-TMY `IrradianceProvider` for tests + dev.

The real adapters (NSRDB / PVGIS / Open-Meteo) need network access and
API keys; this fake builds a clear-sky TMY directly from pvlib's
analytic clear-sky models so engine tests can run pvlib's ModelChain
end-to-end without touching the network.

We intentionally use a clear-sky baseline (Ineichen) so the synthetic
year is bright and stable — this is for round-trip tests, not for
modeling accuracy benchmarks.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
from pvlib.location import Location

from backend.providers.irradiance import HOURS_PER_TMY, IrradianceSource, TmyData


class FakeIrradianceProvider:
    """Generates a synthetic clear-sky 8760 TMY for any lat/lon."""

    name: IrradianceSource = "openmeteo"

    def __init__(self, *, timezone: str = "UTC", elevation_m: float = 100.0) -> None:
        self._timezone = timezone
        self._elevation_m = elevation_m

    async def fetch_tmy(self, lat: float, lon: float) -> TmyData:
        return synthetic_tmy(
            lat=lat,
            lon=lon,
            timezone=self._timezone,
            elevation_m=self._elevation_m,
        )


def synthetic_tmy(
    *,
    lat: float,
    lon: float,
    timezone: str = "UTC",
    elevation_m: float = 100.0,
    temp_air_c: float = 15.0,
    wind_speed_m_s: float = 1.0,
) -> TmyData:
    """Construct a clear-sky 8760 TMY at ``lat``/``lon``.

    The clear-sky GHI/DNI/DHI come from pvlib's Ineichen model; air
    temperature and wind speed are constants — sufficient for engine
    correctness tests that don't care about realistic seasonal swings.
    """
    naive_hours = pd.DatetimeIndex(
        [datetime(2023, 1, 1, 0, tzinfo=UTC) + timedelta(hours=i) for i in range(HOURS_PER_TMY)]
    )
    index = naive_hours.tz_convert(timezone)
    location = Location(latitude=lat, longitude=lon, tz=timezone, altitude=elevation_m)
    clear_sky = location.get_clearsky(index, model="ineichen")

    return TmyData(
        lat=lat,
        lon=lon,
        elevation_m=elevation_m,
        timezone=timezone,
        source="openmeteo",
        fetched_at=datetime.now(UTC),
        ghi_w_m2=[float(v) for v in clear_sky["ghi"].tolist()],
        dni_w_m2=[float(v) for v in clear_sky["dni"].tolist()],
        dhi_w_m2=[float(v) for v in clear_sky["dhi"].tolist()],
        temp_air_c=[temp_air_c] * HOURS_PER_TMY,
        wind_speed_m_s=[wind_speed_m_s] * HOURS_PER_TMY,
    )
