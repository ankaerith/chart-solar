"""Feature-flag-aware step registry.

A step registers under a feature key (e.g. ``engine.battery.hourly_dispatch``);
the registry decides at runtime whether to include the step based on the
caller's tier. Keeps engine composition declarative.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

StepFn = Callable[..., Any]


@dataclass(frozen=True)
class StepRegistration:
    feature_key: str
    fn: StepFn


_STEPS: list[StepRegistration] = []


def register(feature_key: str) -> Callable[[StepFn], StepFn]:
    def decorator(fn: StepFn) -> StepFn:
        _STEPS.append(StepRegistration(feature_key=feature_key, fn=fn))
        return fn

    return decorator


def steps_for(feature_keys: set[str]) -> list[StepRegistration]:
    return [s for s in _STEPS if s.feature_key in feature_keys]
