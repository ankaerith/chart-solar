"""State incentive seed provider tests.

Locks in: every required state shows up; federal ITC rides along on
state queries; date-window filtering matches by install_date; stale
flag mirrors the URDB seed's policy.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.providers.incentive import IncentiveQuery
from backend.providers.incentive.state_seed import (
    StateIncentiveSeedProvider,
    is_stale,
    load_seed,
)

#: Minimum jurisdiction set the bead requires the seed to cover. Each
#: of these gets at least one incentive entry; federal ITC ("US")
#: rides along on every state-scoped query.
EXPECTED_STATE_JURISDICTIONS: set[str] = {
    "US-NY",
    "US-MA",
    "US-CO",
    "US-OR",
    "US-NJ",
    "US-MD",
    "US-PA",
    "US-DC",
    "US-OH",
}


def test_seed_loads_and_validates() -> None:
    seed = load_seed()
    assert seed.schema_version >= 1
    assert seed.refresh_cadence_days >= 30
    assert seed.stale_warning_days >= 30
    assert any(i.jurisdiction == "US" and i.type == "federal_itc" for i in seed.incentives)


def test_seed_covers_required_states() -> None:
    provider = StateIncentiveSeedProvider()
    assert EXPECTED_STATE_JURISDICTIONS.issubset(provider.jurisdictions)


@pytest.mark.parametrize("state", sorted(EXPECTED_STATE_JURISDICTIONS))
async def test_each_state_query_includes_federal_itc(state: str) -> None:
    """Federal ITC must ride along on every state-scoped query — it's
    the headline incentive on any US install and missing it would
    silently halve the audit's NPV."""
    provider = StateIncentiveSeedProvider()
    incentives = await provider.fetch(
        IncentiveQuery(jurisdiction=state, install_date=date(2026, 6, 1))
    )
    federal = [i for i in incentives if i.type == "federal_itc"]
    assert len(federal) == 1
    assert federal[0].amount == pytest.approx(0.30)
    assert federal[0].amount_kind == "pct_system_cost"


@pytest.mark.parametrize("state", sorted(EXPECTED_STATE_JURISDICTIONS))
async def test_each_state_query_includes_at_least_one_state_program(state: str) -> None:
    provider = StateIncentiveSeedProvider()
    incentives = await provider.fetch(
        IncentiveQuery(jurisdiction=state, install_date=date(2026, 6, 1))
    )
    state_only = [i for i in incentives if i.jurisdiction == state]
    assert state_only, f"no state-scoped programs returned for {state!r}"


async def test_install_date_before_start_excludes_program() -> None:
    """Federal ITC starts 2023-01-01; an install date before that must
    not return it."""
    provider = StateIncentiveSeedProvider()
    incentives = await provider.fetch(
        IncentiveQuery(jurisdiction="US-NY", install_date=date(2020, 1, 1))
    )
    assert not any(i.type == "federal_itc" for i in incentives)


async def test_install_date_after_end_excludes_program() -> None:
    """Federal ITC ends 2032-12-31; an install date after that must
    not return it (the post-2032 step-down lands as a separate entry
    once Congress finalises it)."""
    provider = StateIncentiveSeedProvider()
    incentives = await provider.fetch(
        IncentiveQuery(jurisdiction="US-NY", install_date=date(2033, 6, 1))
    )
    assert not any(i.type == "federal_itc" for i in incentives)


async def test_jurisdiction_isolation() -> None:
    """A NY query must not return a CA or NJ entry — startswith() is
    prefix-based, so a leaked-but-falsely-matching entry would be
    picked up here."""
    provider = StateIncentiveSeedProvider()
    incentives = await provider.fetch(
        IncentiveQuery(jurisdiction="US-NY", install_date=date(2026, 6, 1))
    )
    foreign = [i for i in incentives if i.jurisdiction not in {"US", "US-NY"}]
    assert not foreign, f"unexpected non-NY entries leaked: {foreign}"


def test_stale_flag_within_window() -> None:
    snapshot = date(2026, 4, 1)
    assert not is_stale(
        snapshot_date=snapshot,
        today=snapshot + timedelta(days=89),
        stale_after_days=90,
    )


def test_stale_flag_after_window() -> None:
    snapshot = date(2026, 1, 1)
    assert is_stale(
        snapshot_date=snapshot,
        today=snapshot + timedelta(days=120),
        stale_after_days=90,
    )


def test_provider_stale_property_reads_from_seed() -> None:
    seed = load_seed()
    fresh = StateIncentiveSeedProvider(seed=seed, today=seed.snapshot_date)
    aged = StateIncentiveSeedProvider(
        seed=seed,
        today=seed.snapshot_date + timedelta(days=seed.stale_warning_days + 1),
    )
    assert not fresh.stale
    assert aged.stale
    assert fresh.snapshot_date == seed.snapshot_date


async def test_srec_states_carry_per_kwh_entries() -> None:
    """SREC-market states must have at least one ``srec`` entry —
    that's the load-bearing line item for those states' headline
    payback figures."""
    provider = StateIncentiveSeedProvider()
    for state in ("US-NJ", "US-MD", "US-PA", "US-DC", "US-OH"):
        incentives = await provider.fetch(
            IncentiveQuery(jurisdiction=state, install_date=date(2026, 6, 1))
        )
        srecs = [i for i in incentives if i.type == "srec"]
        assert srecs, f"{state!r} expected at least one SREC entry"
        assert all(i.amount_kind == "per_kwh" for i in srecs)
