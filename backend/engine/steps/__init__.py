"""Pipeline steps.

Each step exposes a pure-math entry point and (where ADR 0006 leaves
one) registers under an ``engine.<step>`` feature key. Importing this
package eagerly imports each step module so its ``register()`` decorator
runs at engine import time — the registration audit (chart-solar-nbwe)
relies on this side effect.

Modules in this package fall into three groups:

* **Implemented + registered**: ``dc_production``, ``degradation``,
  ``tariff``, ``export_credit`` — real Phase-1a entry points hooked
  into the pipeline orchestrator (chart-solar-cm4i).
* **Pipeline-aware stubs**: ``soiling``, ``snow`` — wrap pvlib's
  models once monthly precipitation / snowfall / RH route through
  ``TmyData`` (chart-solar-743 / chart-solar-9ji blocked on
  chart-solar-dvc4). ``cell_temperature`` and ``clipping`` are
  permanently stubbed: pvlib's ModelChain handles them inside
  ``dc_production`` (ADR 0006).
* **Phase-1a in-flight**: ``consumption``, ``battery_dispatch``,
  ``finance``, ``monte_carlo``, ``irradiance`` — implementations
  arrive as their respective beads close.
"""

from backend.engine.steps import (
    battery_dispatch,
    clipping,
    consumption,
    dc_production,
    degradation,
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
    "finance",
    "irradiance",
    "monte_carlo",
    "snow",
    "soiling",
    "tariff",
    "temperature",
]
