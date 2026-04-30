"""Hand-curated state-level incentive provider.

Bundles a snapshot of high-traffic state programs (NY, MA, CO, OR, NJ,
MD, PA, DC, OH) plus the federal ITC. DSIRE integration is deferred to
Phase 3a pending counsel review on CC-BY-SA; this is the launch-day
baseline drawn from each state energy office's public program pages,
cross-checked against DSIRE for shape but not embedded from it.

Every entry is date-parameterized: ``start_date`` / ``end_date`` are
honoured by ``IncentiveQuery.install_date`` so a stepped-down program
that closed last year doesn't quietly inflate today's forecast. Future
step-downs land as separate forward-dated entries (e.g. NY-Sun's next
block) rather than in-place edits, so a re-opened audit reproduces the
rate that applied at original quote time.

Like the URDB seed, the snapshot embeds ``snapshot_date`` +
``stale_warning_days``; ``StateIncentiveSeedProvider.stale`` exposes a
single boolean for the audit's "rate may be outdated" banner.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from importlib import resources

from pydantic import BaseModel, Field, ValidationError

from backend.providers.incentive import Incentive, IncentiveQuery, incentive_applies

#: Resource path inside ``backend.providers.incentive`` for the seed.
SEED_RESOURCE_PACKAGE = "backend.providers.incentive.seed_data"
SEED_RESOURCE_FILENAME = "state_incentives_2026q2.json"


class StateIncentiveSeed(BaseModel):
    """The seed file's top-level shape.

    Pydantic validation runs at load — a malformed snapshot fails
    immediately rather than at the first ``.fetch()`` call.
    """

    schema_version: int = Field(..., ge=1)
    snapshot_date: date
    snapshot_label: str
    source: str
    refresh_cadence_days: int = Field(..., ge=1)
    stale_warning_days: int = Field(..., ge=1)
    notes: list[str] = Field(default_factory=list)
    incentives: list[Incentive]


@lru_cache(maxsize=1)
def load_seed() -> StateIncentiveSeed:
    """Read + validate the bundled JSON snapshot.

    Loads via ``importlib.resources`` so the file is found whether the
    package is installed from source or from a wheel. Raises a flat
    ``ValueError`` (not the bare Pydantic ``ValidationError``) so
    callers can catch one type for any seed-load failure. Cached because
    the snapshot is a build-time constant — re-reading on every
    ``StateIncentiveSeedProvider`` instantiation is wasted I/O.
    """
    raw = resources.files(SEED_RESOURCE_PACKAGE).joinpath(SEED_RESOURCE_FILENAME).read_text()
    payload = json.loads(raw)
    try:
        return StateIncentiveSeed.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Incentive seed {SEED_RESOURCE_FILENAME!r} is malformed") from exc


def is_stale(*, snapshot_date: date, today: date, stale_after_days: int) -> bool:
    """``True`` once the snapshot is older than its configured window."""
    return (today - snapshot_date) > timedelta(days=stale_after_days)


class StateIncentiveSeedProvider:
    """``IncentiveProvider``-compatible adapter over the bundled seed.

    Returns every incentive whose jurisdiction prefixes the query
    jurisdiction and whose date window contains ``install_date``.
    Federal-ITC ("US") rides along on every state-scoped query.
    """

    name: str = "state-incentive-seed"

    def __init__(
        self,
        seed: StateIncentiveSeed | None = None,
        *,
        today: date | None = None,
    ) -> None:
        self._seed = seed if seed is not None else load_seed()
        self._today = today or date.today()

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

    @property
    def jurisdictions(self) -> set[str]:
        """Distinct jurisdiction codes covered by the seed (handy for
        the audit UI's "we have curated data for these states" copy)."""
        return {inc.jurisdiction for inc in self._seed.incentives}

    async def fetch(self, query: IncentiveQuery) -> list[Incentive]:
        return [inc for inc in self._seed.incentives if incentive_applies(inc, query)]


__all__ = [
    "SEED_RESOURCE_FILENAME",
    "SEED_RESOURCE_PACKAGE",
    "StateIncentiveSeed",
    "StateIncentiveSeedProvider",
    "is_stale",
    "load_seed",
]
