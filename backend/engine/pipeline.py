"""Engine pipeline.

Each step is a pure function ``(state) -> state``. The pipeline composes
them in order; steps register themselves with the registry under a
feature key so promotion/demotion between tiers is config, not code.

Phase 0: pass-through scaffolding. Real steps land in Phase 1a.
"""

from dataclasses import dataclass, field
from typing import Any

from backend.engine.inputs import ForecastInputs


@dataclass
class ForecastState:
    inputs: ForecastInputs
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass
class ForecastResult:
    inputs: ForecastInputs
    artifacts: dict[str, Any]


def run_forecast(inputs: ForecastInputs) -> ForecastResult:
    state = ForecastState(inputs=inputs)
    # Phase 1a: iterate engine.registry steps here.
    return ForecastResult(inputs=state.inputs, artifacts=state.artifacts)
