"""Shared boilerplate for bundled-seed providers.

`UrdbSeedProvider` and `StateIncentiveSeedProvider` (and any future
seeded provider) share the same shape: an `importlib.resources` JSON
load, a Pydantic root model with a `snapshot_date` + `stale_warning_days`,
and `snapshot_date` / `stale` properties on the provider class. Hoist
that here so domain-specific providers carry only the parts that vary.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, timedelta
from importlib import resources
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ValidationError


@runtime_checkable
class _SeedWithStaleness(Protocol):
    snapshot_date: date
    stale_warning_days: int


def is_stale(*, snapshot_date: date, today: date, stale_after_days: int) -> bool:
    """``True`` once a seed snapshot is older than its configured window.

    Surfaces in the audit so users know to treat seed-derived numbers
    as approximate when the underlying source has likely been
    superseded.
    """
    return (today - snapshot_date) > timedelta(days=stale_after_days)


def load_seed_resource[TSeed: BaseModel](
    *,
    package: str,
    filename: str,
    model: type[TSeed],
    transform: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> TSeed:
    """Read + validate a bundled JSON seed file.

    Loads via ``importlib.resources`` so the file is found whether the
    package is checked out or installed from a wheel. Optional
    ``transform`` runs on the parsed dict before model validation —
    URDB uses it to flatten ``utilities[].rates[]`` into a flat list.
    Pydantic ``ValidationError`` is wrapped in ``ValueError`` so callers
    catch one type for any seed-load failure.
    """
    raw = resources.files(package).joinpath(filename).read_text()
    payload: dict[str, Any] = json.loads(raw)
    if transform is not None:
        payload = transform(payload)
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Seed {filename!r} is malformed") from exc


class BundledSeedProvider[TSeed: _SeedWithStaleness]:
    """Mixin that adds ``snapshot_date`` + ``stale`` given ``_seed`` + ``_today``.

    Subclasses parameterize on their seed model and must set
    ``self._seed`` + ``self._today`` in ``__init__``. The seed model
    must expose ``snapshot_date: date`` and ``stale_warning_days: int``.
    """

    _seed: TSeed
    _today: date

    @property
    def snapshot_date(self) -> date:
        return self._seed.snapshot_date

    @property
    def stale(self) -> bool:
        return is_stale(
            snapshot_date=self._seed.snapshot_date,
            today=self._today,
            stale_after_days=self._seed.stale_warning_days,
        )


__all__ = ["BundledSeedProvider", "is_stale", "load_seed_resource"]
