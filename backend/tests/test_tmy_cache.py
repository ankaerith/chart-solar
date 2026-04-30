"""Postgres-backed TMY cache (chart-solar-wx1).

Covers three layers:

1. ``bucket_lat_lon`` rounds to 4 decimal places exactly across
   roundtrips through Decimal — float-equality false misses are the
   exact failure mode we're guarding against.
2. ``store_cached_tmy`` + ``lookup_cached_tmy`` UPSERT roundtrip
   (re-fetching a bucket overwrites the prior row, doesn't duplicate).
3. ``forecast_worker._fetch_tmy_async`` consults the cache before the
   provider — second call for the same bucket skips the network.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import asyncpg
import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import OperationalError

import backend.database as _db
from backend.db.tmy_cache import (
    BUCKET_DECIMAL_PLACES,
    IRRADIANCE_ATTRIBUTION,
    TmyCache,
    bucket_lat_lon,
    lookup_cached_tmy,
    store_cached_tmy,
)
from backend.providers.fake import synthetic_tmy
from backend.providers.irradiance import IrradianceSource, TmyData


@pytest.fixture(scope="module", autouse=True)
async def _require_postgres() -> None:
    try:
        async with _db.SessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except (OperationalError, asyncpg.exceptions.PostgresError, ConnectionError, OSError) as exc:
        pytest.skip(f"Postgres not reachable at DATABASE_URL: {exc}")


@pytest.fixture
async def clean_tmy_cache() -> AsyncIterator[None]:
    async with _db.SessionLocal() as session:
        await session.execute(delete(TmyCache))
        await session.commit()
    yield
    async with _db.SessionLocal() as session:
        await session.execute(delete(TmyCache))
        await session.commit()


def _sample_tmy(*, lat: float, lon: float, source: IrradianceSource) -> TmyData:
    """Build a TmyData by retagging the synthetic clear-sky generator —
    sidesteps the network without losing the channel-length validation."""
    base = synthetic_tmy(lat=lat, lon=lon)
    return base.model_copy(update={"source": source, "fetched_at": datetime.now(UTC)})


# ---- bucket math ------------------------------------------------------


def test_bucket_lat_lon_rounds_to_four_decimal_places() -> None:
    lat_b, lon_b = bucket_lat_lon(33.456789, -112.073412)
    assert lat_b == Decimal("33.4568")
    assert lon_b == Decimal("-112.0734")
    # Both buckets carry exactly the configured number of decimal places.
    # ``as_tuple().exponent`` returns ``int`` for finite Decimals (and a
    # special-form literal for nan/inf, which we never produce here).
    lat_exp = lat_b.as_tuple().exponent
    lon_exp = lon_b.as_tuple().exponent
    assert isinstance(lat_exp, int) and isinstance(lon_exp, int)
    assert -lat_exp == BUCKET_DECIMAL_PLACES
    assert -lon_exp == BUCKET_DECIMAL_PLACES


def test_bucket_lat_lon_collapses_sub_bucket_jitter() -> None:
    """Two lat/lon pairs that differ only past the 4th decimal place
    must collapse to the same bucket — that's the whole point of the
    cache key."""
    a = bucket_lat_lon(33.45670, -112.07340)
    b = bucket_lat_lon(33.45674, -112.07339)
    assert a == b


def test_bucket_lat_lon_distinguishes_at_eleven_meters() -> None:
    """Roughly 0.0001 deg ≈ 11 m at the equator. Two locations that
    differ in the 4th decimal place must land in different buckets."""
    a = bucket_lat_lon(33.4567, -112.0734)
    b = bucket_lat_lon(33.4568, -112.0734)
    assert a != b


# ---- attribution registry --------------------------------------------


def test_attribution_registry_covers_every_source() -> None:
    """The IrradianceSource Literal lists three providers; the
    attribution registry must carry one entry per source so a
    ``store_cached_tmy`` call never KeyErrors at runtime."""
    expected_sources = {"nsrdb", "pvgis", "openmeteo"}
    assert set(IRRADIANCE_ATTRIBUTION.keys()) == expected_sources
    for license_str, attribution in IRRADIANCE_ATTRIBUTION.values():
        assert license_str
        assert attribution


# ---- store / lookup roundtrip ---------------------------------------


async def test_store_and_lookup_roundtrip(clean_tmy_cache: None) -> None:
    tmy = _sample_tmy(lat=33.4568, lon=-112.0734, source="openmeteo")

    async with _db.SessionLocal() as session:
        await store_cached_tmy(session, tmy)

    async with _db.SessionLocal() as session:
        cached = await lookup_cached_tmy(
            session,
            lat=33.4568,
            lon=-112.0734,
            source="openmeteo",
        )

    assert cached is not None
    assert cached.lat == pytest.approx(tmy.lat)
    assert cached.lon == pytest.approx(tmy.lon)
    assert cached.source == "openmeteo"
    assert cached.ghi_w_m2 == tmy.ghi_w_m2  # full payload survives JSONB roundtrip


async def test_lookup_returns_none_on_miss(clean_tmy_cache: None) -> None:
    async with _db.SessionLocal() as session:
        cached = await lookup_cached_tmy(session, lat=10.0, lon=20.0, source="nsrdb")
    assert cached is None


async def test_lookup_misses_other_source_at_same_bucket(clean_tmy_cache: None) -> None:
    """Source bucket separation: an NSRDB row at this bucket must not
    serve a PVGIS lookup. License changes at one provider need to
    invalidate only that provider's slice."""
    nsrdb_tmy = _sample_tmy(lat=33.4568, lon=-112.0734, source="nsrdb")
    async with _db.SessionLocal() as session:
        await store_cached_tmy(session, nsrdb_tmy)

    async with _db.SessionLocal() as session:
        pvgis_lookup = await lookup_cached_tmy(session, lat=33.4568, lon=-112.0734, source="pvgis")
    assert pvgis_lookup is None


async def test_store_is_upsert(clean_tmy_cache: None) -> None:
    """A second store at the same (bucket, source) overwrites — the
    primary key is the lookup contract, so duplicate rows would corrupt
    the cache invariant."""
    first = _sample_tmy(lat=33.4568, lon=-112.0734, source="openmeteo")
    later = _sample_tmy(lat=33.4568, lon=-112.0734, source="openmeteo").model_copy(
        update={"fetched_at": datetime(2030, 1, 1, tzinfo=UTC)}
    )

    async with _db.SessionLocal() as session:
        await store_cached_tmy(session, first)
        await store_cached_tmy(session, later)

    async with _db.SessionLocal() as session:
        rows = (await session.execute(text("SELECT count(*) FROM tmy_cache"))).scalar_one()
    assert rows == 1


async def test_store_writes_attribution_metadata(clean_tmy_cache: None) -> None:
    """The cache row must carry source_license + attribution_string so
    a methodology export can serve attribution off the row without
    re-deriving from the application registry (which may have shifted
    between fetch and read)."""
    tmy = _sample_tmy(lat=33.4568, lon=-112.0734, source="openmeteo")
    async with _db.SessionLocal() as session:
        await store_cached_tmy(session, tmy)

    async with _db.SessionLocal() as session:
        row_attrs = (
            await session.execute(
                text(
                    "SELECT source_license, attribution_string "
                    "FROM tmy_cache WHERE source = 'openmeteo'"
                )
            )
        ).one()

    expected_license, expected_attribution = IRRADIANCE_ATTRIBUTION["openmeteo"]
    assert row_attrs[0] == expected_license
    assert row_attrs[1] == expected_attribution


async def test_lookup_uses_bucketed_lat_lon(clean_tmy_cache: None) -> None:
    """A user request 11 meters away from the cached bucket should hit
    the same row — that's the whole point of bucketing."""
    cached_tmy = _sample_tmy(lat=33.4568, lon=-112.0734, source="openmeteo")
    async with _db.SessionLocal() as session:
        await store_cached_tmy(session, cached_tmy)

    async with _db.SessionLocal() as session:
        # Sub-bucket jitter — same 4-decimal bucket.
        result = await lookup_cached_tmy(
            session, lat=33.45680001, lon=-112.07339999, source="openmeteo"
        )
    assert result is not None


# ---- worker integration ---------------------------------------------


async def test_worker_fetch_tmy_writes_cache_on_miss_and_reuses_on_hit(
    clean_tmy_cache: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``forecast_worker._fetch_tmy_async`` must consult the cache
    before calling the live provider, and write the result back on a
    miss. The contract: a second forecast at the same bucket goes
    through one provider call total, not two."""

    from backend.engine.inputs import (
        FinancialInputs,
        ForecastInputs,
        SystemInputs,
        TariffInputs,
    )
    from backend.workers import forecast_worker

    inputs = ForecastInputs(
        system=SystemInputs(lat=33.4568, lon=-112.0734, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(),
        tariff=TariffInputs(country="US"),
    )

    fetch_count = 0

    class _CountingProvider:
        name: IrradianceSource = "openmeteo"

        async def fetch_tmy(self, lat: float, lon: float) -> TmyData:
            nonlocal fetch_count
            fetch_count += 1
            return _sample_tmy(lat=lat, lon=lon, source="openmeteo")

    monkeypatch.setattr(forecast_worker, "pick_provider", lambda lat, lon: _CountingProvider())

    # First call: cache miss → provider runs.
    first = await forecast_worker._fetch_tmy_async(inputs)
    assert first.source == "openmeteo"
    assert fetch_count == 1

    # Second call at the same bucket: cache hit → provider should not
    # be touched again.
    second = await forecast_worker._fetch_tmy_async(inputs)
    assert second.source == "openmeteo"
    assert fetch_count == 1, "second forecast must not re-fetch from provider"

    # Same bucket, sub-bucket jitter: still a hit.
    jittered = inputs.model_copy(
        update={
            "system": inputs.system.model_copy(update={"lat": 33.45680001, "lon": -112.07339999})
        }
    )
    third = await forecast_worker._fetch_tmy_async(jittered)
    assert third.source == "openmeteo"
    assert fetch_count == 1
