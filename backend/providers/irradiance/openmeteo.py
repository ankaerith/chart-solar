"""Open-Meteo adapter — global fallback.

Free tier:  https://archive-api.open-meteo.com/v1/archive  (no key)
Paid tier:  https://customer-archive-api.open-meteo.com/v1/archive
            requires an API key, switched on by `OPENMETEO_PAID_ENABLED`
            (€29/mo Standard plan per PRODUCT_PLAN.md § Weather).

We don't get a true TMY from Open-Meteo — we synthesise one by pulling
a single representative recent year (the most recently completed
calendar year) at hourly resolution. That's adequate for v1 and matches
what the existing single-user repo does.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from backend.infra.http import make_get
from backend.providers.irradiance import HOURS_PER_TMY, IrradianceSource, TmyData

OPENMETEO_FREE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPENMETEO_PAID_URL = "https://customer-archive-api.open-meteo.com/v1/archive"


class OpenMeteoProvider:
    """Open-Meteo Historical Weather archive — global, free or paid tier."""

    name: IrradianceSource = "openmeteo"

    def __init__(
        self,
        *,
        paid_enabled: bool = False,
        api_key: str | None = None,
    ) -> None:
        self._paid_enabled = paid_enabled
        self._api_key = api_key
        self._get = make_get(service="openmeteo")

    @property
    def endpoint(self) -> str:
        return OPENMETEO_PAID_URL if self._paid_enabled else OPENMETEO_FREE_URL

    async def fetch_tmy(self, lat: float, lon: float) -> TmyData:
        if self._paid_enabled and not self._api_key:
            raise RuntimeError(
                "OpenMeteoProvider: paid tier enabled but `openmeteo_paid_api_key` is unset"
            )
        year = _representative_year()
        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31",
            "hourly": ",".join(
                [
                    "shortwave_radiation",
                    "direct_normal_irradiance",
                    "diffuse_radiation",
                    "temperature_2m",
                    "wind_speed_10m",
                ]
            ),
            "timezone": "GMT",
        }
        if self._paid_enabled and self._api_key:
            params["apikey"] = self._api_key

        response = await self._get(self.endpoint, params=params)
        return parse_openmeteo_json(response.json(), source_lat=lat, source_lon=lon)


def parse_openmeteo_json(
    payload: dict[str, Any],
    *,
    source_lat: float,
    source_lon: float,
) -> TmyData:
    """Parse Open-Meteo Archive JSON. Pure."""
    elevation = float(payload.get("elevation", 0.0))
    timezone = payload.get("timezone", "UTC") or "UTC"

    hourly = payload.get("hourly", {})
    ghi = [float(v or 0.0) for v in hourly.get("shortwave_radiation", [])]
    dni = [float(v or 0.0) for v in hourly.get("direct_normal_irradiance", [])]
    dhi = [float(v or 0.0) for v in hourly.get("diffuse_radiation", [])]
    temp = [float(v or 0.0) for v in hourly.get("temperature_2m", [])]
    wind = [float(v or 0.0) for v in hourly.get("wind_speed_10m", [])]

    # Open-Meteo returns 8784 hours in a leap year and 8760 otherwise.
    # We trim Feb-29 in leap years to produce a consistent 8760 TMY.
    if len(ghi) == 8784:
        ghi, dni, dhi, temp, wind = (
            _drop_feb29(ghi),
            _drop_feb29(dni),
            _drop_feb29(dhi),
            _drop_feb29(temp),
            _drop_feb29(wind),
        )

    if len(ghi) != HOURS_PER_TMY:
        raise ValueError(f"Open-Meteo payload had {len(ghi)} hourly rows; expected {HOURS_PER_TMY}")

    return TmyData(
        lat=source_lat,
        lon=source_lon,
        elevation_m=elevation,
        timezone=timezone,
        source="openmeteo",
        fetched_at=datetime.now(UTC),
        ghi_w_m2=ghi,
        dni_w_m2=dni,
        dhi_w_m2=dhi,
        temp_air_c=temp,
        wind_speed_m_s=wind,
    )


def _representative_year() -> int:
    """Most recently completed calendar year — Open-Meteo's archive
    extends through ~5 days of lag, so the last fully-closed year is
    a safe choice."""
    today = date.today()
    return today.year - 1


def _drop_feb29(series: list[float]) -> list[float]:
    """Drop the 24 hours starting Feb 29 00:00 (hour index 1416..1439)."""
    feb29_start = (31 + 28) * 24  # day-of-year for Feb 29 00:00 in a leap year
    return series[:feb29_start] + series[feb29_start + 24 :]
