"""Deterministic in-memory `IncentiveProvider`.

Ships a tiny built-in table covering the US federal ITC and UK SEG so
the engine has *something* to chew on out of the box; tests register
extra rows via `.add()`."""

from __future__ import annotations

from datetime import date

from backend.providers.incentive import (
    Incentive,
    IncentiveProvider,
    IncentiveQuery,
)


class FakeIncentiveProvider:
    """All registered incentives that match `(jurisdiction, install_date)`
    are returned. Catalog is mutable via `.add()` for test-time setup."""

    name: str = "fake-incentive"

    def __init__(self) -> None:
        self._catalog: list[Incentive] = [
            Incentive(
                name="Federal Investment Tax Credit",
                type="federal_itc",
                jurisdiction="US",
                amount=0.30,
                amount_kind="pct_system_cost",
                start_date=date(2023, 1, 1),
                end_date=date(2032, 12, 31),
            ),
            Incentive(
                name="UK Smart Export Guarantee (placeholder)",
                type="uk_seg",
                jurisdiction="GB",
                amount=0.15,
                amount_kind="per_kwh",
                start_date=date(2020, 1, 1),
            ),
        ]

    def add(self, incentive: Incentive) -> None:
        self._catalog.append(incentive)

    async def fetch(self, query: IncentiveQuery) -> list[Incentive]:
        return [incentive for incentive in self._catalog if _applies(incentive, query)]


def _applies(incentive: Incentive, query: IncentiveQuery) -> bool:
    if not query.jurisdiction.startswith(incentive.jurisdiction):
        return False
    if incentive.start_date and query.install_date < incentive.start_date:
        return False
    return not (incentive.end_date and query.install_date > incentive.end_date)


_: IncentiveProvider = FakeIncentiveProvider()
