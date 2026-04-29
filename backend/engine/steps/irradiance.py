"""Engine step: fetch hourly TMY for the system's lat/lon.

The actual provider implementations (NSRDB / PVGIS / Open-Meteo) live
in `backend/providers/irradiance/`; this module is the engine-side
entry point. `pick_provider` auto-routes by lat/lon — see
`backend/providers/irradiance/__init__.py` for the routing table.

Postgres lat/lon-bucket caching (chart-solar-wx1) wraps this layer
once it lands; until then the engine pays the upstream call cost on
every run.
"""

from __future__ import annotations

from backend.providers.irradiance import (
    HOURS_PER_TMY,
    IrradianceProvider,
    IrradianceSource,
    TmyData,
    pick_provider,
)

__all__ = [
    "HOURS_PER_TMY",
    "IrradianceProvider",
    "IrradianceSource",
    "TmyData",
    "pick_provider",
]
