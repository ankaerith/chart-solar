"""Step-registry audit: every Phase-1a engine step exposes its canonical
entry point under an ``engine.<step>`` feature key.

This is a registry-completeness check, not a behavioural one. ADR 0006
supersedes ``engine.cell_temperature`` and ``engine.clipping`` (handled
inside ``engine.dc_production`` by pvlib's ModelChain), and parks
``engine.soiling`` until pvlib's HSU model gets PM2.5 / PM10 columns
on ``TmyData``.
"""

from __future__ import annotations

import backend.engine.steps  # noqa: F401  triggers @register decorators
from backend.engine.registry import _STEPS, steps_for

EXPECTED_KEYS: set[str] = {
    "engine.dc_production",
    "engine.snow",
    "engine.degradation",
    "engine.tariff",
    "engine.export_credit",
    "engine.finance",
}

# Per ADR 0006, these steps must NOT register a top-level entry point:
# the physics is inside `engine.dc_production`'s ModelChain run, and a
# separate step would either no-op or double-count.
SUPERSEDED_KEYS: set[str] = {
    "engine.cell_temperature",
    "engine.clipping",
}

# Soiling stays deferred until the irradiance providers carry PM2.5 +
# PM10 columns (pvlib's HSU model is the published soiling routine and
# requires them). When the data layer lands, drop this from the set
# and add the key to EXPECTED_KEYS.
DEFERRED_KEYS: set[str] = {
    "engine.soiling",
}


def _registered_keys() -> set[str]:
    return {step.feature_key for step in _STEPS}


def test_expected_engine_keys_are_registered() -> None:
    registered = _registered_keys()
    missing = EXPECTED_KEYS - registered
    assert not missing, f"engine steps missing @register: {sorted(missing)}"


def test_superseded_keys_are_not_registered() -> None:
    registered = _registered_keys()
    leaked = SUPERSEDED_KEYS & registered
    assert not leaked, (
        "ADR 0006 forbids a top-level registration for these keys "
        f"(re-handle inside engine.dc_production): {sorted(leaked)}"
    )


def test_deferred_keys_are_not_registered_yet() -> None:
    registered = _registered_keys()
    leaked = DEFERRED_KEYS & registered
    assert not leaked, (
        "engine.soiling is a stub until pvlib-quality PM2.5 / PM10 "
        f"weather inputs land — see ADR 0006: {sorted(leaked)}"
    )


def test_steps_for_filters_to_the_requested_keys() -> None:
    selected = steps_for({"engine.dc_production", "engine.degradation"})
    assert {s.feature_key for s in selected} == {
        "engine.dc_production",
        "engine.degradation",
    }


def test_steps_for_unknown_key_returns_empty() -> None:
    assert steps_for({"engine.nonexistent"}) == []


def test_each_registered_step_has_callable_entrypoint() -> None:
    for step in _STEPS:
        assert callable(step.fn), f"{step.feature_key} entry point is not callable"
