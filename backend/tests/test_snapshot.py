"""Snapshot pinning — version + content hashes for reproducibility."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from backend.engine.snapshot import (
    Snapshot,
    build_snapshot,
    current_engine_version,
    current_pvlib_version,
    hash_canonical,
)

# ---------------------------------------------------------------------------
# hash_canonical
# ---------------------------------------------------------------------------


def test_hash_canonical_is_whitespace_and_key_order_insensitive() -> None:
    a = {"a": 1, "b": [2, 3], "c": "x"}
    b = {"c": "x", "a": 1, "b": [2, 3]}
    assert hash_canonical(a) == hash_canonical(b)


def test_hash_canonical_changes_on_value_change() -> None:
    a = {"price": 30_000.0}
    b = {"price": 30_001.0}
    assert hash_canonical(a) != hash_canonical(b)


def test_hash_canonical_handles_pydantic_models() -> None:
    class Sample(BaseModel):
        x: float
        y: str

    a = Sample(x=1.0, y="hello")
    b = Sample(x=1.0, y="hello")
    assert hash_canonical(a) == hash_canonical(b)
    assert hash_canonical(a) == hash_canonical({"x": 1.0, "y": "hello"})


def test_hash_canonical_handles_datetime_via_default_str() -> None:
    """datetime serialises through the JSONEncoder fallback so
    snapshots can hash inputs that include timestamps."""
    a = {"fetched_at": datetime(2026, 4, 29, tzinfo=UTC)}
    b = {"fetched_at": datetime(2026, 4, 29, tzinfo=UTC)}
    assert hash_canonical(a) == hash_canonical(b)


def test_hash_canonical_returns_hex_digest_length_64() -> None:
    digest = hash_canonical({"x": 1})
    assert len(digest) == 64
    int(digest, 16)  # parses as hex


# ---------------------------------------------------------------------------
# Version pickers
# ---------------------------------------------------------------------------


def test_current_engine_version_is_a_string() -> None:
    v = current_engine_version()
    assert isinstance(v, str)
    assert v != ""


def test_current_pvlib_version_matches_imported() -> None:
    import pvlib

    assert current_pvlib_version() == str(pvlib.__version__)


# ---------------------------------------------------------------------------
# Snapshot equality / matches semantics
# ---------------------------------------------------------------------------


def _sample_snapshot(**overrides: object) -> Snapshot:
    base = {
        "engine_version": "0.0.0",
        "pvlib_version": "0.15.1",
        "irradiance_source": "pvgis",
        "irradiance_fetched_at": datetime(2026, 4, 1, tzinfo=UTC),
        "tariff_hash": "a" * 64,
        "inputs_hash": "b" * 64,
    }
    base.update(overrides)
    return Snapshot(**base)


def test_snapshot_matches_ignores_created_at() -> None:
    """Two snapshots with the same content but different `created_at`
    must compare equal — otherwise the cache invalidates pointlessly."""
    s1 = _sample_snapshot()
    s2 = _sample_snapshot()
    assert s1.matches(s2)
    # Even when explicitly different created_at:
    s3 = _sample_snapshot()
    s3 = s3.model_copy(update={"created_at": datetime(2030, 1, 1, tzinfo=UTC)})
    assert s1.matches(s3)


def test_snapshot_matches_distinguishes_each_pin() -> None:
    base = _sample_snapshot()

    # engine_version drift → mismatch
    assert not base.matches(_sample_snapshot(engine_version="0.0.1"))
    # pvlib_version drift → mismatch
    assert not base.matches(_sample_snapshot(pvlib_version="0.16.0"))
    # irradiance source change → mismatch
    assert not base.matches(_sample_snapshot(irradiance_source="nsrdb"))
    # irradiance fetched_at change → mismatch (a re-fetch invalidates)
    assert not base.matches(
        _sample_snapshot(irradiance_fetched_at=datetime(2026, 4, 2, tzinfo=UTC))
    )
    # tariff_hash drift → mismatch
    assert not base.matches(_sample_snapshot(tariff_hash="c" * 64))
    # inputs_hash drift → mismatch
    assert not base.matches(_sample_snapshot(inputs_hash="d" * 64))


def test_snapshot_round_trips_through_json() -> None:
    s = _sample_snapshot()
    serialised = s.model_dump(mode="json")
    revived = Snapshot.model_validate(serialised)
    assert revived.matches(s)


def test_snapshot_validates_hash_lengths() -> None:
    with pytest.raises(ValueError):
        _sample_snapshot(tariff_hash="too-short")
    with pytest.raises(ValueError):
        _sample_snapshot(inputs_hash="too-short")


# ---------------------------------------------------------------------------
# build_snapshot
# ---------------------------------------------------------------------------


def test_build_snapshot_uses_live_versions_and_hashes_inputs() -> None:
    fetched_at = datetime(2026, 4, 1, 12, tzinfo=UTC)
    inputs = {"system": {"dc_kw": 8.0}, "tilt": 22.0, "azimuth": 180.0}
    tariff = {"name": "PSE Schedule 7", "flat_rate_per_kwh": 0.13}

    snap = build_snapshot(
        inputs=inputs,
        tariff=tariff,
        irradiance_source="pvgis",
        irradiance_fetched_at=fetched_at,
    )

    assert snap.engine_version == current_engine_version()
    assert snap.pvlib_version == current_pvlib_version()
    assert snap.irradiance_source == "pvgis"
    assert snap.irradiance_fetched_at == fetched_at
    assert snap.tariff_hash == hash_canonical(tariff)
    assert snap.inputs_hash == hash_canonical(inputs)


def test_build_snapshot_two_identical_calls_match() -> None:
    """Determinism check: run build_snapshot twice with identical
    inputs; the matches() invariant holds (created_at differs but is
    explicitly excluded from matches)."""
    fetched_at = datetime(2026, 4, 1, 12, tzinfo=UTC)
    inputs = {"system": {"dc_kw": 8.0}}
    tariff = {"flat_rate_per_kwh": 0.13}

    s1 = build_snapshot(
        inputs=inputs,
        tariff=tariff,
        irradiance_source="nsrdb",
        irradiance_fetched_at=fetched_at,
    )
    s2 = build_snapshot(
        inputs=inputs,
        tariff=tariff,
        irradiance_source="nsrdb",
        irradiance_fetched_at=fetched_at,
    )
    assert s1.matches(s2)


def test_build_snapshot_input_change_breaks_match() -> None:
    fetched_at = datetime(2026, 4, 1, tzinfo=UTC)
    s1 = build_snapshot(
        inputs={"system": {"dc_kw": 8.0}},
        tariff={"x": 1},
        irradiance_source="nsrdb",
        irradiance_fetched_at=fetched_at,
    )
    s2 = build_snapshot(
        inputs={"system": {"dc_kw": 9.0}},
        tariff={"x": 1},
        irradiance_source="nsrdb",
        irradiance_fetched_at=fetched_at,
    )
    assert not s1.matches(s2)


def test_build_snapshot_tariff_change_breaks_match() -> None:
    fetched_at = datetime(2026, 4, 1, tzinfo=UTC)
    s1 = build_snapshot(
        inputs={"x": 1},
        tariff={"flat_rate_per_kwh": 0.13},
        irradiance_source="nsrdb",
        irradiance_fetched_at=fetched_at,
    )
    s2 = build_snapshot(
        inputs={"x": 1},
        tariff={"flat_rate_per_kwh": 0.18},
        irradiance_source="nsrdb",
        irradiance_fetched_at=fetched_at,
    )
    assert not s1.matches(s2)
