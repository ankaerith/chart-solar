"""Open-Meteo adapter — global fallback.

Free tier:  https://archive-api.open-meteo.com/v1/archive  (no key)
Paid tier:  https://customer-archive-api.open-meteo.com/v1/archive
            requires an API key, switched on by `OPENMETEO_PAID_ENABLED`
            (€29/mo Standard plan per PRODUCT_PLAN.md § Weather).

Open-Meteo doesn't ship a true TMY — we synthesise one by pulling the
most recently completed calendar year hourly.
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
    elevation = float(payload.get("elevation", 0.0))
    timezone = payload.get("timezone", "UTC") or "UTC"

    hourly = payload.get("hourly", {})
    channels = {
        "ghi": _channel(hourly, "shortwave_radiation"),
        "dni": _channel(hourly, "direct_normal_irradiance"),
        "dhi": _channel(hourly, "diffuse_radiation"),
        "temp": _channel(hourly, "temperature_2m"),
        "wind": _channel(hourly, "wind_speed_10m"),
    }
    if len(channels["ghi"]) == 8784:
        # Leap year — trim Feb 29 so v1 always sees a consistent 8760 TMY.
        channels = {k: _drop_feb29(v) for k, v in channels.items()}

    ghi = channels["ghi"]
    if len(ghi) != HOURS_PER_TMY:
        raise ValueError(f"Open-Meteo payload had {len(ghi)} hourly rows; expected {HOURS_PER_TMY}")

    return TmyData(
        lat=source_lat,
        lon=source_lon,
        elevation_m=elevation,
        timezone=timezone,
        source="openmeteo",
        fetched_at=datetime.now(UTC),
        ghi_w_m2=channels["ghi"],
        dni_w_m2=channels["dni"],
        dhi_w_m2=channels["dhi"],
        temp_air_c=channels["temp"],
        wind_speed_m_s=channels["wind"],
    )


def _channel(hourly: dict[str, Any], key: str) -> list[float]:
    return [float(v or 0.0) for v in hourly.get(key, [])]


def _representative_year() -> int:
    # Open-Meteo's archive lags by a few days, so the most recently
    # completed calendar year is the safe choice.
    return date.today().year - 1


def _drop_feb29(series: list[float]) -> list[float]:
    feb29_start = (31 + 28) * 24
    return series[:feb29_start] + series[feb29_start + 24 :]
