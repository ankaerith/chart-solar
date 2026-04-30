"""URDB-seeded ``TariffProvider`` tests.

Locks in the seed file's contract: every top-10 utility key resolves
to a non-empty schedule that round-trips through the engine's billing
primitives, and the stale-flag policy is consistent across snapshot
ages. Bills the synthesized schedule against a flat 1 kWh/hr load to
catch shape errors that the schema validator alone wouldn't notice.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.engine.steps.tariff import compute_annual_bill
from backend.providers.irradiance import HOURS_PER_TMY
from backend.providers.tariff import TariffQuery
from backend.providers.tariff.urdb import (
    UrdbSeedProvider,
    is_stale,
    load_seed,
)

#: The exact set of utility keys the bead requires the seed to cover —
#: tested as a hard equality so an accidental omission shows up here.
EXPECTED_UTILITY_KEYS: set[str] = {
    "PGE",
    "SCE",
    "SDGE",
    "PSE",
    "XCEL_CO",
    "FPL",
    "DUKE_NC",
    "APS",
    "SRP",
    "CONED",
}


def test_seed_loads_and_validates() -> None:
    """Schema-level validation runs at load — catches a malformed
    snapshot before any caller sees a half-broken provider."""
    seed = load_seed()
    assert seed.schema_version >= 1
    assert seed.refresh_cadence_days >= 30
    assert seed.stale_warning_days >= 30
    assert len(seed.rates) >= len(EXPECTED_UTILITY_KEYS)


def test_seed_covers_top_10_utilities() -> None:
    provider = UrdbSeedProvider()
    keys = set(provider.utilities())
    assert keys == EXPECTED_UTILITY_KEYS


@pytest.mark.parametrize("utility_key", sorted(EXPECTED_UTILITY_KEYS))
async def test_each_utility_resolves_to_a_billable_schedule(utility_key: str) -> None:
    """Each seeded utility must round-trip a full year of billing
    without a tariff-validator error or a structure mismatch."""
    provider = UrdbSeedProvider()
    schedule = await provider.fetch(TariffQuery(country="US", utility=utility_key))
    assert schedule.utility
    assert schedule.currency == "USD"

    hourly_load = [1.0] * HOURS_PER_TMY  # 1 kWh/hr → 8760 kWh/yr
    bill = compute_annual_bill(hourly_net_load_kwh=hourly_load, tariff=schedule)
    assert bill.annual_kwh_imported == pytest.approx(HOURS_PER_TMY)
    assert bill.annual_total > 0
    # Fixed monthly charge contributes 12× per year, regardless of structure.
    expected_fixed = schedule.fixed_monthly_charge * 12
    assert bill.annual_fixed_charge == pytest.approx(expected_fixed)


async def test_unknown_utility_raises() -> None:
    """Unknown utility keys raise rather than silently returning a
    default — catches typos at the call site."""
    provider = UrdbSeedProvider()
    with pytest.raises(LookupError, match="not_a_real_utility"):
        await provider.fetch(TariffQuery(country="US", utility="not_a_real_utility"))


async def test_query_without_utility_raises() -> None:
    provider = UrdbSeedProvider()
    with pytest.raises(LookupError, match="utility key"):
        await provider.fetch(TariffQuery(country="US"))


async def test_utility_lookup_is_case_insensitive() -> None:
    provider = UrdbSeedProvider()
    upper = await provider.fetch(TariffQuery(country="US", utility="PGE"))
    lower = await provider.fetch(TariffQuery(country="US", utility="pge"))
    assert upper.utility == lower.utility


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
    """The provider exposes a single ``.stale`` property so callers
    don't re-derive the policy at every render."""
    seed = load_seed()
    fresh = UrdbSeedProvider(seed=seed, today=seed.snapshot_date)
    aged = UrdbSeedProvider(
        seed=seed, today=seed.snapshot_date + timedelta(days=seed.stale_warning_days + 1)
    )
    assert not fresh.stale
    assert aged.stale
    assert fresh.snapshot_date == seed.snapshot_date


def test_pge_tou_billing_separates_peak_from_off_peak() -> None:
    """Sanity smoke for the headline TOU rate: a load that runs only
    during PG&E E-TOU-C peak hours bills at the peak rate, not off-peak."""
    seed = load_seed()
    provider = UrdbSeedProvider(seed=seed)
    import asyncio

    schedule = asyncio.run(provider.fetch(TariffQuery(country="US", utility="PGE")))
    assert schedule.tou_periods is not None

    # 1 kWh in every 4-9pm hour, zero everywhere else (weekday peak only;
    # tariff billing applies the weekday hour mask).
    peak_only = [0.0] * HOURS_PER_TMY
    for hour in range(HOURS_PER_TMY):
        if (hour % 24) in {16, 17, 18, 19, 20}:
            peak_only[hour] = 1.0
    bill = compute_annual_bill(hourly_net_load_kwh=peak_only, tariff=schedule)

    peak_rate = max(p.rate_per_kwh for p in schedule.tou_periods)
    off_peak_rate = min(p.rate_per_kwh for p in schedule.tou_periods)
    assert peak_rate > off_peak_rate
    energy_only = bill.annual_energy_charge
    assert energy_only == pytest.approx(bill.annual_kwh_imported * peak_rate, rel=1e-3)
