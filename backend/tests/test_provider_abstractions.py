"""Provider Protocols + matching `Fake*` impls.

The point of these tests isn't to exercise every adapter under the sun
(those land per-bead — j47, cvn, dws, c1q, csm). It's to prove that:

* the four Protocols (`TariffProvider`, `IncentiveProvider`,
  `GeocodingProvider`, `MonitoringProvider`) have stable contracts,
* `backend/providers/fake/` ships a working in-memory adapter for each,
* a consumer typed against the Protocol can swap one fake for another
  with zero code change — that's acceptance criterion 6.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from backend.providers.fake import (
    FakeGeocodingProvider,
    FakeIncentiveProvider,
    FakeMonitoringProvider,
    FakeTariffProvider,
)
from backend.providers.geocoding import GeocodedLocation, GeocodingProvider
from backend.providers.incentive import (
    Incentive,
    IncentiveProvider,
    IncentiveQuery,
)
from backend.providers.monitoring import (
    MonitoringProvider,
    MonitoringReading,
    MonitoringSite,
)
from backend.providers.tariff import (
    TariffProvider,
    TariffQuery,
    TariffSchedule,
    TouPeriod,
)

# ---------------------------------------------------------------------------
# TariffProvider
# ---------------------------------------------------------------------------


async def test_fake_tariff_returns_country_default() -> None:
    p: TariffProvider = FakeTariffProvider()
    schedule = await p.fetch(TariffQuery(country="US"))
    assert schedule.country == "US"
    assert schedule.currency == "USD"
    assert schedule.flat_rate_per_kwh == pytest.approx(0.16)


async def test_fake_tariff_register_overrides_default() -> None:
    p = FakeTariffProvider()
    custom = TariffSchedule(
        name="Custom TOU",
        utility="util-x",
        country="US",
        currency="USD",
        structure="tou",
        flat_rate_per_kwh=None,
        tou_periods=[
            TouPeriod(
                name="peak",
                rate_per_kwh=0.42,
                months=list(range(1, 13)),
                hour_mask=[i in range(16, 21) for i in range(24)],
            ),
        ],
    )
    p.register(TariffQuery(country="US", utility="util-x", zip_code="80302"), custom)

    fetched = await p.fetch(TariffQuery(country="US", utility="util-x", zip_code="80302"))
    assert fetched is custom
    # An unrelated query still gets the default — registry is namespaced.
    fallback = await p.fetch(TariffQuery(country="US"))
    assert fallback.flat_rate_per_kwh == pytest.approx(0.16)


async def test_fake_tariff_unknown_country_raises() -> None:
    p = FakeTariffProvider()
    with pytest.raises(LookupError, match="no default for country"):
        await p.fetch(TariffQuery(country="JP"))


def test_tariff_schedule_validates_structure_consistency() -> None:
    with pytest.raises(ValueError, match="flat tariff requires"):
        TariffSchedule(name="x", utility="x", structure="flat")
    with pytest.raises(ValueError, match="tiered tariff requires"):
        TariffSchedule(name="x", utility="x", structure="tiered")
    with pytest.raises(ValueError, match="tou tariff requires"):
        TariffSchedule(name="x", utility="x", structure="tou")


# ---------------------------------------------------------------------------
# IncentiveProvider
# ---------------------------------------------------------------------------


async def test_fake_incentive_us_returns_federal_itc_in_window() -> None:
    p: IncentiveProvider = FakeIncentiveProvider()
    incentives = await p.fetch(IncentiveQuery(jurisdiction="US-CA", install_date=date(2026, 6, 1)))
    types = {i.type for i in incentives}
    assert "federal_itc" in types


async def test_fake_incentive_excludes_expired_window() -> None:
    p = FakeIncentiveProvider()
    incentives = await p.fetch(IncentiveQuery(jurisdiction="US", install_date=date(2050, 1, 1)))
    # Federal ITC ends 2032-12-31 in the seed catalog.
    assert all(i.type != "federal_itc" for i in incentives)


async def test_fake_incentive_uk_returns_seg() -> None:
    p = FakeIncentiveProvider()
    incentives = await p.fetch(IncentiveQuery(jurisdiction="GB", install_date=date(2026, 6, 1)))
    assert any(i.type == "uk_seg" for i in incentives)


async def test_fake_incentive_add_lets_tests_inject_rows() -> None:
    p = FakeIncentiveProvider()
    p.add(
        Incentive(
            name="Custom Rebate",
            type="utility_rebate",
            jurisdiction="US-CO",
            amount=500.0,
            amount_kind="fixed_amount",
        )
    )
    incentives = await p.fetch(IncentiveQuery(jurisdiction="US-CO", install_date=date(2026, 6, 1)))
    assert any(i.name == "Custom Rebate" for i in incentives)


# ---------------------------------------------------------------------------
# GeocodingProvider
# ---------------------------------------------------------------------------


async def test_fake_geocoding_known_landmarks() -> None:
    p: GeocodingProvider = FakeGeocodingProvider()
    boulder = await p.geocode("Boulder, CO")
    assert boulder.country == "US"
    assert boulder.lat == pytest.approx(40.0150)


async def test_fake_geocoding_unknown_falls_back_to_hash() -> None:
    p = FakeGeocodingProvider()
    a = await p.geocode("123 Made-Up Lane, Nowhere")
    b = await p.geocode("123 Made-Up Lane, Nowhere")
    # Same input → same coords (deterministic).
    assert a == b
    assert -60.0 <= a.lat <= 60.0
    assert -180.0 <= a.lon <= 180.0


async def test_fake_geocoding_reverse_finds_known_landmarks() -> None:
    p = FakeGeocodingProvider()
    london = await p.reverse(51.5074, -0.1278)
    assert london.country == "GB"


async def test_fake_geocoding_reverse_falls_back_for_unknown() -> None:
    p = FakeGeocodingProvider()
    out = await p.reverse(0.0, 0.0)
    assert out.country == "ZZ"


# ---------------------------------------------------------------------------
# MonitoringProvider
# ---------------------------------------------------------------------------


async def test_fake_monitoring_round_trips_readings() -> None:
    p: MonitoringProvider = FakeMonitoringProvider()
    p_typed = p
    assert isinstance(p_typed, FakeMonitoringProvider)
    p_typed.add_site(
        MonitoringSite(
            site_id="site-1",
            name="Test Roof",
            timezone="America/Los_Angeles",
            dc_kw=8.0,
        )
    )
    p_typed.add_readings(
        "site-1",
        [
            MonitoringReading(
                timestamp_utc=datetime(2026, 6, 1, 12, tzinfo=UTC),
                energy_kwh=4.2,
            ),
            MonitoringReading(
                timestamp_utc=datetime(2026, 6, 2, 13, tzinfo=UTC),
                energy_kwh=5.1,
            ),
        ],
    )

    sites = await p.list_sites(credential={"key": "ignored"})
    assert len(sites) == 1
    assert sites[0].site_id == "site-1"

    readings = await p.fetch_production(
        credential={"key": "ignored"},
        site_id="site-1",
        start=date(2026, 6, 1),
        end=date(2026, 6, 1),
    )
    assert len(readings) == 1
    assert readings[0].energy_kwh == pytest.approx(4.2)


async def test_fake_monitoring_unknown_site_raises() -> None:
    p = FakeMonitoringProvider()
    with pytest.raises(LookupError, match="unknown monitoring site"):
        await p.fetch_production(
            credential={},
            site_id="missing",
            start=date(2026, 6, 1),
            end=date(2026, 6, 30),
        )


# ---------------------------------------------------------------------------
# DI swap test (acceptance criterion 6)
# ---------------------------------------------------------------------------


async def consumer_quotes_first_year_bill(
    provider: TariffProvider,
    annual_kwh: float,
    *,
    country: str = "US",
) -> float:
    """Stand-in for the engine's tariff step. Deliberately knows nothing
    about *which* TariffProvider it got — it only depends on the
    Protocol contract."""
    schedule = await provider.fetch(TariffQuery(country=country))
    monthly_charge = schedule.fixed_monthly_charge * 12
    if schedule.flat_rate_per_kwh is None:
        raise RuntimeError("consumer only supports flat schedules in this stub")
    return monthly_charge + annual_kwh * schedule.flat_rate_per_kwh


async def test_swap_tariff_provider_requires_zero_consumer_change() -> None:
    """Swapping the source of TariffSchedule (default fake → custom-registered
    fake) must change the consumer's output without changing its code.
    Demonstrates the Protocol-based DI surface."""

    # Start with the default fake (US default = $0.16/kWh, $10/mo).
    default_provider = FakeTariffProvider()
    default_bill = await consumer_quotes_first_year_bill(default_provider, annual_kwh=12_000)
    assert default_bill == pytest.approx(120.0 + 1_920.0)

    # Swap to a different fake that returns a cheaper schedule for the
    # same query — the consumer code is unchanged.
    cheap_provider = FakeTariffProvider()
    cheap_provider.register(
        TariffQuery(country="US"),
        TariffSchedule(
            name="Cheap default",
            utility="cheap-util",
            country="US",
            currency="USD",
            structure="flat",
            fixed_monthly_charge=5.0,
            flat_rate_per_kwh=0.10,
        ),
    )
    cheap_bill = await consumer_quotes_first_year_bill(cheap_provider, annual_kwh=12_000)
    assert cheap_bill == pytest.approx(60.0 + 1_200.0)
    assert cheap_bill < default_bill


# ---------------------------------------------------------------------------
# Sanity: every Fake satisfies its Protocol via runtime_checkable.
# ---------------------------------------------------------------------------


def test_fakes_satisfy_their_protocols() -> None:
    assert isinstance(FakeTariffProvider(), TariffProvider)
    assert isinstance(FakeIncentiveProvider(), IncentiveProvider)
    assert isinstance(FakeGeocodingProvider(), GeocodingProvider)
    assert isinstance(FakeMonitoringProvider(), MonitoringProvider)


def test_geocoded_location_validates_lat_lon_range() -> None:
    with pytest.raises(ValueError):
        GeocodedLocation(lat=999.0, lon=0.0, formatted_address="bad", country="US")
