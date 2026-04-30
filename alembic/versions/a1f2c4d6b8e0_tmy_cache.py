"""tmy_cache: postgres-backed lat/lon-bucket TMY cache

Revision ID: a1f2c4d6b8e0
Revises: 8b3e7a1c4d20
Create Date: 2026-04-29 19:00:00.000000
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
