"""tmy_cache: postgres-backed lat/lon-bucket TMY cache (chart-solar-wx1)

Revision ID: a1f2c4d6b8e0
Revises: 8b3e7a1c4d20
Create Date: 2026-04-29 19:00:00.000000

Caches the 8760-hour TMY payload returned by NSRDB / PVGIS / Open-Meteo
keyed by 4-decimal lat/lon (~11 m bucket) × source. The cache is a
pure performance optimisation — the engine pipeline is deterministic
given the same TmyData, so a hit lets a re-run skip the network fetch.

Source bucket separation: the primary key includes ``source``, so a
license change at one provider invalidates only that slice (we delete
the rows tagged with that source, leave the other providers intact).
``source_license`` + ``attribution_string`` are stored on the cache row
itself so the attribution surfacing in API responses + methodology
exports can be served straight off the row without re-deriving from a
hardcoded registry.

The TMY payload travels as JSONB. The 8760-entry float arrays are
small enough that JSONB beats a separate ``tmy_hours`` table on every
axis (lookup latency, write latency, query simplicity). At 8760 hours
× 5 channels × ~8 bytes ≈ 350 kB per row uncompressed — Postgres
TOAST handles this cleanly for any reasonable row count.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1f2c4d6b8e0"
down_revision: str | Sequence[str] | None = "8b3e7a1c4d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tmy_cache",
        # 4-decimal place lat/lon = ~11 m bucket. Numeric chosen over
        # double precision so the bucket key is exact across roundtrips
        # — float comparison would risk false misses on identical inputs.
        sa.Column("lat_bucket", sa.Numeric(7, 4), nullable=False),
        sa.Column("lon_bucket", sa.Numeric(8, 4), nullable=False),
        # nsrdb / pvgis / openmeteo. Stored as text so a future provider
        # can land without an enum migration; the application-side
        # IrradianceSource Literal is the source of truth on values.
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_license", sa.String(length=128), nullable=False),
        sa.Column("attribution_string", sa.Text(), nullable=False),
        # Original lat/lon as supplied (for debugging — the bucket
        # rounds 33.4567 and 33.45670001 to the same row).
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column(
            "tmy_data",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "lat_bucket",
            "lon_bucket",
            "source",
            name="pk_tmy_cache",
        ),
    )
    # Index on source alone supports the "invalidate one provider's
    # slice when license changes" admin operation.
    op.create_index("ix_tmy_cache_source", "tmy_cache", ["source"])


def downgrade() -> None:
    op.drop_index("ix_tmy_cache_source", table_name="tmy_cache")
    op.drop_table("tmy_cache")
