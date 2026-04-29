"""Snapshot pinning — every saved forecast / audit is reproducible.

A `Snapshot` captures the version + content state the engine consumed
when it produced a result. Re-opening a saved forecast re-runs only if
the live snapshot diverges; otherwise the cached result is served. The
methodology PDF reads from these pins so "this $/W came from PVGIS on
2026-04-12 against this exact tariff schedule" is traceable.
"""

from __future__ import annotations

import functools
import hashlib
import json
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from typing import Any, Literal

import pvlib
from pydantic import BaseModel, Field

# Mirrors the `IrradianceSource` Literal in `backend.providers.irradiance`;
# kept local so this module imports cleanly before that package lands. The
# duplication collapses to one source of truth once both branches merge.
IrradianceSource = Literal["nsrdb", "pvgis", "openmeteo"]

ENGINE_PACKAGE_NAME = "chart-solar-backend"

_PVLIB_VERSION: str = str(pvlib.__version__)


class Snapshot(BaseModel):
    """One reproducibility receipt: pinned versions + content hashes."""

    engine_version: str
    pvlib_version: str
    irradiance_source: IrradianceSource
    irradiance_fetched_at: datetime
    tariff_hash: str = Field(..., min_length=64, max_length=64)
    inputs_hash: str = Field(..., min_length=64, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def matches(self, other: Snapshot) -> bool:
        """True when two snapshots are cache-equivalent.

        Compares everything *except* `created_at` — two snapshots minutes
        apart with identical state must match so the cache stays warm.
        Excluding via `model_dump` rather than a hand-listed field set
        means a new pin added to the model is automatically covered.
        """
        excluded = {"created_at"}
        return self.model_dump(exclude=excluded) == other.model_dump(exclude=excluded)


@functools.lru_cache(maxsize=1)
def current_engine_version() -> str:
    """Live package version, cached forever — package metadata can't
    change at runtime. Falls back to ``"unknown"`` when running from an
    editable tree without installed metadata."""
    try:
        return _package_version(ENGINE_PACKAGE_NAME)
    except PackageNotFoundError:
        return "unknown"


def current_pvlib_version() -> str:
    return _PVLIB_VERSION


def hash_canonical(value: Any) -> str:
    """sha256 of canonical JSON — whitespace + key-order insensitive.

    Pydantic models go through `model_dump(mode="json")`; everything else
    is fed straight to `json.dumps(sort_keys=True, default=str)` so
    `datetime` / `Decimal` / similar stragglers serialise without a
    custom encoder.
    """
    if isinstance(value, BaseModel):
        payload: Any = value.model_dump(mode="json")
    else:
        payload = value
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_snapshot(
    *,
    inputs: Any,
    tariff: Any,
    irradiance_source: IrradianceSource,
    irradiance_fetched_at: datetime,
) -> Snapshot:
    """Picks up live versions, canonicalises + hashes inputs and tariff."""
    return Snapshot(
        engine_version=current_engine_version(),
        pvlib_version=current_pvlib_version(),
        irradiance_source=irradiance_source,
        irradiance_fetched_at=irradiance_fetched_at,
        tariff_hash=hash_canonical(tariff),
        inputs_hash=hash_canonical(inputs),
    )
