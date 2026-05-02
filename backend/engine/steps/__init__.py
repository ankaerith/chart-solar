"""Pipeline steps.

Each step exposes a pure-math entry point and (where ADR 0006 leaves
one) registers under an ``engine.<step>`` feature key. Importing this
package eagerly imports each step module so its ``register()`` decorator
runs at engine import time — the registration audit relies on this
side effect.

Modules in this package fall into three groups:

* **Implemented + registered**: ``dc_production``, ``degradation``,
  ``tariff``, ``export_credit``, ``snow``, ``finance`` — real Phase-1a
  entry points hooked into the pipeline orchestrator. ``snow`` consumes
  the monthly snowfall + RH columns on ``TmyData`` and wraps pvlib's
  Townsend model.
* **Pipeline-aware stubs**: ``soiling`` — wraps pvlib's HSU model once
  PM2.5 + PM10 columns route through ``TmyData``. ``cell_temperature``
  and ``clipping`` are permanently stubbed: pvlib's ModelChain handles
  them inside ``dc_production`` (ADR 0006).
* **Phase-1a in-flight**: ``consumption``, ``battery_dispatch``,
  ``monte_carlo`` — implementations arrive as their respective beads
  close. The TMY fetch is the worker's responsibility (network IO,
  async); the engine consumes pre-fetched ``TmyData`` via
  ``backend.domain.tmy`` and never has its own irradiance step.
"""

from backend.engine.steps import (
    battery_dispatch,
    clipping,
    consumption,
    dc_production,
    degradation,
    export_credit,
    finance,
    monte_carlo,
    snow,
    soiling,
    tariff,
    temperature,
    tornado,
)

__all__ = [
    "battery_dispatch",
    "clipping",
    "consumption",
    "dc_production",
    "degradation",
    "export_credit",
    "finance",
    "monte_carlo",
    "snow",
    "soiling",
    "tariff",
    "temperature",
    "tornado",
]
