"""Snapshot pinning — every saved forecast / audit is reproducible.

A `Snapshot` captures the *complete* set of versions and content
hashes the engine consumed when it produced a result. When the user
re-opens a saved forecast we re-run the engine only if the live
snapshot differs; otherwise the cached result is served verbatim. The
methodology PDF reads from this so "this $/W came from PVGIS on
2026-04-12 against this exact tariff schedule" is traceable.

The four pins per PRODUCT_PLAN.md § Snapshots are versioned:

* `engine_version` — the chart-solar package version (from
  pyproject.toml via importlib.metadata)
* `pvlib_version` — pvlib's version (live import; pinned in uv.lock)
* `irradiance_source` + `irradiance_fetched_at` — which provider gave
  the TMY, and when (so a re-fetch invalidates the snapshot)
* `tariff_hash` — sha256 of the canonical-JSON tariff schedule (a
  rate-card change invalidates the snapshot even if every other input
  is unchanged)
* `inputs_hash` — sha256 of the user-supplied inputs (system size,
  tilt, financing, etc.); covers any input the engine reads.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from typing import Any, Literal

from pydantic import BaseModel, Field

# Mirrors the `IrradianceSource` Literal in `backend.providers.irradiance`.
# Duplicated here so this module stays importable from any branch — the
# provider package lands separately and the registry is small enough that
# keeping it in two places is cheaper than the cross-branch coupling.
IrradianceSource = Literal["nsrdb", "pvgis", "openmeteo"]

ENGINE_PACKAGE_NAME = "chart-solar-backend"


class Snapshot(BaseModel):
    """A reproducibility receipt for one engine run.

    Two snapshots from the same inputs run on the same code MUST be
    equal — `model_dump()` is the canonical comparison form. The
    `inputs_hash` + `tariff_hash` + `irradiance_*` fields capture
    everything the engine reads; the version fields capture the code
    that processed it.
    """

    engine_version: str
    pvlib_version: str
    irradiance_source: IrradianceSource
    irradiance_fetched_at: datetime
    tariff_hash: str = Field(..., min_length=64, max_length=64)
    inputs_hash: str = Field(..., min_length=64, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def matches(self, other: Snapshot) -> bool:
        """Are these two snapshots interchangeable?

        Equal versions + equal hashes + equal irradiance fetch identity
        → yes. `created_at` is intentionally NOT part of the match —
        two snapshots an hour apart with otherwise-identical state
        should compare equal so we don't re-run the engine pointlessly.
        """
        return (
            self.engine_version == other.engine_version
            and self.pvlib_version == other.pvlib_version
            and self.irradiance_source == other.irradiance_source
            and self.irradiance_fetched_at == other.irradiance_fetched_at
            and self.tariff_hash == other.tariff_hash
            and self.inputs_hash == other.inputs_hash
        )


def current_engine_version() -> str:
    """Read the live package version. Falls back to ``"unknown"`` when
    the package isn't installed (e.g., running from an editable source
    tree before `uv sync` has populated metadata)."""
    try:
        return _package_version(ENGINE_PACKAGE_NAME)
    except PackageNotFoundError:
        return "unknown"


def current_pvlib_version() -> str:
    """Read pvlib's version live. We don't cache because pvlib pins
    rarely move and the cost is one attribute lookup."""
    import pvlib

    return str(pvlib.__version__)


def hash_canonical(value: Any) -> str:
    """sha256 of the canonical-JSON representation of `value`.

    Pydantic models go through `model_dump(mode="json")` first.
    Dicts / lists / scalars are dumped via `json.dumps(sort_keys=True,
    separators=(",", ":"))` so equivalent inputs hash equal regardless
    of whitespace or key order. `default=str` catches stragglers like
    `datetime` and `Decimal`."""
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
    """One-call constructor: canonicalises + hashes both inputs and
    the tariff schedule, picks up live versions for engine + pvlib."""
    return Snapshot(
        engine_version=current_engine_version(),
        pvlib_version=current_pvlib_version(),
        irradiance_source=irradiance_source,
        irradiance_fetched_at=irradiance_fetched_at,
        tariff_hash=hash_canonical(tariff),
        inputs_hash=hash_canonical(inputs),
    )
