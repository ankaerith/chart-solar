from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import backend.database as _db
from backend.config import settings
from backend.db import Base
from backend.db.audit_models import Audit
from backend.engine.inputs import (
    FinancialInputs,
    ForecastInputs,
    SystemInputs,
    TariffInputs,
)
from backend.entitlements.guards import current_user_id
from backend.main import app

#: Materialized views the audit migration adds. ``Base.metadata`` doesn't
#: track these (matviews aren't ORM tables), so ``drop_all`` would fail
#: with ``DependentObjectsStillExistError`` whenever a prior alembic run
#: left them behind. We drop them first so cleanup is idempotent across
#: pytest ↔ alembic sequences.
_MATERIALIZED_VIEWS: tuple[str, ...] = (
    "region_pricing_aggregates",
    "installer_internal_stats",
)

#: Stable per-session test users. Auth tests pin Alice and Bob via the
#: ``current_user_id`` dependency override so route-level access checks
#: see two distinct subjects without going through magic-link auth.
ALICE_USER_ID = uuid.uuid4()
BOB_USER_ID = uuid.uuid4()


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
            for matview in _MATERIALIZED_VIEWS:
                await conn.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {matview} CASCADE"))
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


@pytest.fixture
def client_alice() -> Iterator[TestClient]:
    """TestClient pinned to ALICE_USER_ID via dependency override."""
    app.dependency_overrides[current_user_id] = lambda: str(ALICE_USER_ID)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(current_user_id, None)


@pytest.fixture
def client_bob() -> Iterator[TestClient]:
    """TestClient pinned to BOB_USER_ID via dependency override."""
    app.dependency_overrides[current_user_id] = lambda: str(BOB_USER_ID)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(current_user_id, None)


@pytest.fixture
def client_anonymous() -> Iterator[TestClient]:
    """TestClient with no override — the auth dep sees the anonymous sentinel."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def db() -> AsyncIterator[Any]:
    """Per-test session that cleans the audit + user tables on exit.

    The cleanup sweep covers ``installer_quotes`` (FK to audits),
    ``audits``, ``user_pii_vault``, and ``users`` so Alice/Bob row
    pollution stays contained as more tests adopt the fixture.
    """
    if _db.SessionLocal is None:
        pytest.skip("Postgres unavailable for integration tests")
    async with _db.SessionLocal() as session:
        yield session
        await session.execute(text("DELETE FROM installer_quotes"))
        await session.execute(text("DELETE FROM audits"))
        await session.execute(text("DELETE FROM user_pii_vault"))
        await session.execute(text("DELETE FROM users"))
        await session.commit()


async def make_audit(session: Any, *, owner: uuid.UUID) -> uuid.UUID:
    """Insert a minimal audit row owned by ``owner`` and return its id."""
    audit = Audit(user_id=owner, location_bucket="98101")
    session.add(audit)
    await session.commit()
    return audit.id
