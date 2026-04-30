"""Bucketed Postgres cache for irradiance-provider TMY responses."""

from __future__ import annotations

from dataclasses import dataclass
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

#: 4 decimal places ≈ 11 m of ground precision, well below the spatial
#: variation of TMY weather products (NSRDB ~4 km, PVGIS ~5 km).
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


@dataclass(frozen=True, slots=True)
class SourceAttribution:
    license: str
    attribution: str


#: Attribution registry. Stored copies on cache rows survive a future
#: registry edit, so existing entries never silently shift their
#: license text — invalidate the row to refresh.
IRRADIANCE_ATTRIBUTION: dict[IrradianceSource, SourceAttribution] = {
    "nsrdb": SourceAttribution(
        license="NREL public data — no commercial restrictions",
        attribution=(
            "Source: NREL National Solar Radiation Database (PSM3). "
            "© Alliance for Sustainable Energy, LLC. "
            "https://nsrdb.nrel.gov/about/data-access"
        ),
    ),
    "pvgis": SourceAttribution(
        license="European Commission JRC — reuse permitted with attribution",
        attribution=(
            "Source: JRC Photovoltaic Geographical Information System (PVGIS) "
            "© European Union, 2001-2024. https://re.jrc.ec.europa.eu/pvg_tools/"
        ),
    ),
    "openmeteo": SourceAttribution(
        license="CC BY 4.0",
        attribution="Source: Open-Meteo (https://open-meteo.com). © Open-Meteo, CC BY 4.0.",
    ),
}


class TmyCache(Base):
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
    """Return the cached TMY for (lat, lon, source) or ``None`` on miss.

    Uses ``model_construct`` to skip Pydantic re-validation of the
    8760×5 float arrays — the payload was validated on write, and the
    JSONB roundtrip preserves float lists exactly. ``fetched_at`` is
    the one field that needs explicit coercion (JSONB serialises
    datetime as ISO string).
    """
    lat_bucket, lon_bucket = bucket_lat_lon(lat, lon)
    stmt = select(TmyCache).where(
        TmyCache.lat_bucket == lat_bucket,
        TmyCache.lon_bucket == lon_bucket,
        TmyCache.source == source,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    data = dict(row.tmy_data)
    data["fetched_at"] = datetime.fromisoformat(data["fetched_at"])
    return TmyData.model_construct(**data)


async def store_cached_tmy(session: AsyncSession, tmy: TmyData) -> None:
    """UPSERT the TMY row for ``(lat_bucket, lon_bucket, tmy.source)``."""
    lat_bucket, lon_bucket = bucket_lat_lon(tmy.lat, tmy.lon)
    attr = IRRADIANCE_ATTRIBUTION[tmy.source]

    stmt = pg_insert(TmyCache).values(
        lat_bucket=lat_bucket,
        lon_bucket=lon_bucket,
        source=tmy.source,
        source_license=attr.license,
        attribution_string=attr.attribution,
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
