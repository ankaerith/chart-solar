"""Pipeline steps. Each is a pure ``(state) -> state`` transform.

Phase 0 stubs map to PRODUCT_PLAN.md § Architecture. Real implementations
land in Phase 1a. Importing this package eagerly imports each step module
so its ``register()`` decorator runs.
"""

from backend.engine.steps import (
    battery_dispatch,
    clipping,
    consumption,
    dc_production,
    degradation,
    export_credit,
    finance,
    irradiance,
    monte_carlo,
    snow,
    soiling,
    tariff,
    temperature,
)

__all__ = [
    "battery_dispatch",
    "clipping",
    "consumption",
    "dc_production",
    "degradation",
    "export_credit",
    "finance",
    "irradiance",
    "monte_carlo",
    "snow",
    "soiling",
    "tariff",
    "temperature",
]
