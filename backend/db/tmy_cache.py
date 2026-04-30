"""TMY cache: bucketed Postgres storage of irradiance-provider TMY responses.

Cache lookups are keyed by ``(lat_bucket, lon_bucket, source)``, where
the buckets are the input lat/lon rounded to 4 decimal places (~11 m).
Source-bucket separation lets us invalidate one provider's slice on a
license change without touching the others; attribution + license
metadata live on the cache row so a downstream methodology export can
surface them without re-deriving from a hardcoded registry.

The row stores the full ``TmyData`` payload as JSONB; at ~350 kB
uncompressed it's small enough that JSONB beats a separate ``tmy_hours``
satellite table on lookup latency, write latency, and query simplicity.

Reference: chart-solar-wx1; PRODUCT_PLAN.md § Weather & Irradiance Data.
"""

from __future__ import annotations

from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from sqlalchemy import DateTime, Float, Numeric, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.providers.irradiance import IrradianceSource, TmyData

#: Number of decimal places to bucket lat/lon at — 4 places ≈ 11 m of
#: ground precision, well below the spatial variation of TMY weather
#: products (NSRDB nominal cell is ~4 km; PVGIS ~5 km).
BUCKET_DECIMAL_PLACES = 4

_BUCKET_QUANTUM = Decimal(10) ** -BUCKET_DECIMAL_PLACES


def bucket_lat_lon(lat: float, lon: float) -> tuple[Decimal, Decimal]:
    """Round lat/lon to the cache's 4-decimal bucket.

    Decimal-typed return so callers can compare for equality across
    roundtrips through Postgres NUMERIC — float comparison would risk
    false misses on identical user inputs that survived a JSON
    serialise/deserialise cycle.
    """
    lat_bucket = Decimal(repr(lat)).quantize(_BUCKET_QUANTUM, rounding=ROUND_HALF_EVEN)
    lon_bucket = Decimal(repr(lon)).quantize(_BUCKET_QUANTUM, rounding=ROUND_HALF_EVEN)
    return lat_bucket, lon_bucket


#: Per-source license + attribution. License terms come from each
#: provider's published terms-of-use page. Updated together with the
#: cache row's stored ``source_license`` / ``attribution_string`` so an
#: existing cache entry never silently shows stale attribution after we
#: re-pin a provider; cache invalidation is the migration path on
#: license-text changes.
IRRADIANCE_ATTRIBUTION: dict[IrradianceSource, tuple[str, str]] = {
    "nsrdb": (
        "NREL public data — no commercial restrictions",
        "Source: NREL National Solar Radiation Database (PSM3). "
        "© Alliance for Sustainable Energy, LLC. "
        "https://nsrdb.nrel.gov/about/data-access",
    ),
    "pvgis": (
        "European Commission JRC — reuse permitted with attribution",
        "Source: JRC Photovoltaic Geographical Information System (PVGIS) "
        "© European Union, 2001-2024. https://re.jrc.ec.europa.eu/pvg_tools/",
    ),
    "openmeteo": (
        "CC BY 4.0",
        "Source: Open-Meteo (https://open-meteo.com). © Open-Meteo, CC BY 4.0.",
    ),
}


class TmyCache(Base):
    """Cached 8760-hour TMY for one (lat_bucket, lon_bucket, source).

    The composite primary key is the lookup contract: a hit returns the
    same ``TmyData`` to every caller that resolves to the same bucket.
    Source-bucket separation means flipping a provider's license invalidates
    only that provider's rows.
    """

    __tablename__ = "tmy_cache"

    lat_bucket: Mapped[Decimal] = mapped_column(Numeric(7, 4), primary_key=True)
    lon_bucket: Mapped[Decimal] = mapped_column(Numeric(8, 4), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_license: Mapped[str] = mapped_column(String(128), nullable=False)
    attribution_string: Mapped[str] = mapped_column(Text, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    tmy_data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


async def lookup_cached_tmy(
    session: AsyncSession,
    *,
    lat: float,
    lon: float,
    source: IrradianceSource,
) -> TmyData | None:
    """Return the cached TMY for (lat, lon, source) or ``None`` on miss."""
    lat_bucket, lon_bucket = bucket_lat_lon(lat, lon)
    stmt = select(TmyCache).where(
        TmyCache.lat_bucket == lat_bucket,
        TmyCache.lon_bucket == lon_bucket,
        TmyCache.source == source,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    return TmyData.model_validate(row.tmy_data)


async def store_cached_tmy(session: AsyncSession, tmy: TmyData) -> None:
    """UPSERT the TMY row for ``(lat_bucket, lon_bucket, tmy.source)``.

    INSERT … ON CONFLICT DO UPDATE: a re-fetch (e.g. provider rotation
    inside the bucket) overwrites the stale entry rather than duplicating.
    Callers serialize attribution from the static ``IRRADIANCE_ATTRIBUTION``
    registry so all rows for one source carry the same license text.
    """
    lat_bucket, lon_bucket = bucket_lat_lon(tmy.lat, tmy.lon)
    license_str, attribution = IRRADIANCE_ATTRIBUTION[tmy.source]

    stmt = pg_insert(TmyCache).values(
        lat_bucket=lat_bucket,
        lon_bucket=lon_bucket,
        source=tmy.source,
        source_license=license_str,
        attribution_string=attribution,
        lat=tmy.lat,
        lon=tmy.lon,
        tmy_data=tmy.model_dump(mode="json"),
        fetched_at=tmy.fetched_at,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["lat_bucket", "lon_bucket", "source"],
        set_={
            "source_license": stmt.excluded.source_license,
            "attribution_string": stmt.excluded.attribution_string,
            "lat": stmt.excluded.lat,
            "lon": stmt.excluded.lon,
            "tmy_data": stmt.excluded.tmy_data,
            "fetched_at": stmt.excluded.fetched_at,
        },
    )
    await session.execute(stmt)
    await session.commit()
