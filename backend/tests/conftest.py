import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import backend.database as _db
from backend.config import settings
from backend.engine.inputs import (
    FinancialInputs,
    ForecastInputs,
    SystemInputs,
    TariffInputs,
)


@pytest.fixture(scope="session", autouse=True)
def _async_db_uses_null_pool() -> None:
    """Tests reuse no connections across event loops.

    `httpx`/`TestClient` runs its handler in its own internal event loop,
    while pytest-asyncio drives async test bodies on a separate session
    loop. The default async pool caches connections on whichever loop
    opened them, so teardown on a sibling loop hits "Future attached to
    a different loop". `NullPool` opens + closes on demand, so every
    connection lives within a single loop's context. Production keeps the
    real pool — this is a tests-only swap.
    """
    test_engine = create_async_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,
    )
    _db.engine = test_engine
    _db.SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
def example_inputs() -> ForecastInputs:
    return ForecastInputs(
        system=SystemInputs(lat=47.6, lon=-122.3, dc_kw=8.0, tilt_deg=25, azimuth_deg=180),
        financial=FinancialInputs(),
        tariff=TariffInputs(country="US"),
    )
