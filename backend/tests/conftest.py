import asyncio
from collections.abc import Iterator

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import backend.database as _db
from backend.config import settings
from backend.db import Base
from backend.engine.inputs import (
    FinancialInputs,
    ForecastInputs,
    SystemInputs,
    TariffInputs,
)


@pytest.fixture(scope="session", autouse=True)
def _async_db_uses_null_pool() -> Iterator[None]:
    """Tests reuse no connections across event loops, and the schema is
    materialised once per session.

    `httpx`/`TestClient` runs its handler in its own internal event loop,
    while pytest-asyncio drives async test bodies on a separate session
    loop. The default async pool caches connections on whichever loop
    opened them, so teardown on a sibling loop hits "Future attached to
    a different loop". `NullPool` opens + closes on demand, so every
    connection lives within a single loop's context. Production keeps the
    real pool — this is a tests-only swap.

    Migrations stay the prod source of truth (the CI workflow runs
    upgrade → downgrade → upgrade in a separate step), but tests don't
    rely on CI ordering — `Base.metadata.create_all` materialises every
    table on the test engine before the first test runs.
    """
    test_engine = create_async_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,
    )
    _db.engine = test_engine
    _db.SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _create_schema() -> None:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _drop_schema() -> None:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()

    schema_was_created = False
    try:
        asyncio.run(_create_schema())
        schema_was_created = True
    except Exception:
        # If Postgres is unreachable, individual tests skip themselves;
        # don't fail the whole session here.
        pass

    yield

    if schema_was_created:
        # Clean up so the alembic round-trip step (CI runs it after
        # pytest) sees an empty database — otherwise the migration's
        # CREATE TABLE collides with the test-time create_all schema.
        try:
            asyncio.run(_drop_schema())
        except Exception:
            pass


@pytest.fixture
def example_inputs() -> ForecastInputs:
    return ForecastInputs(
        system=SystemInputs(lat=47.6, lon=-122.3, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(),
        tariff=TariffInputs(country="US"),
    )
