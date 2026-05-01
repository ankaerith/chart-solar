"""PDF TTL purge tests — sweep + storage delete + idempotency.

Three scenarios per chart-solar-98cd:

* Happy path: an aged row's PDF gets deleted from storage, the row's
  ``raw_pdf_storage_url`` nulls out, and ``raw_pdf_purged_at`` stamps.
* Already-purged: a row whose URL is already null is skipped (idempotent).
* Storage-deletion failure: the row's URL stays put so the next sweep
  retries; the failure is counted in the sweep result.

Plus boundary cases: rows newer than the TTL aren't touched; the sweep
respects ``batch_size``; a missing-object delete (storage already gone)
is treated as success and the row still purges.

The tests use ``FakeStorageProvider`` so nothing reaches the network.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, text

import backend.database as _db
from backend.db.audit_models import Audit, Installer, InstallerQuote
from backend.providers.fake import FakeStorageProvider
from backend.providers.storage import StorageError
from backend.services.pdf_ttl_purge import (
    purge_expired_pdfs,
    storage_key_from_url,
)


@pytest.fixture
async def db() -> AsyncIterator[Any]:
    if _db.SessionLocal is None:
        pytest.skip("Postgres unavailable for integration tests")
    async with _db.SessionLocal() as session:
        yield session
        await session.execute(text("DELETE FROM installer_quotes"))
        await session.execute(text("DELETE FROM audits"))
        await session.execute(text("DELETE FROM installers"))
        await session.commit()


async def _make_audit_and_installer(session: Any) -> tuple[uuid.UUID, uuid.UUID]:
    audit = Audit()
    installer = Installer(canonical_name="Test Installer")
    session.add_all([audit, installer])
    await session.commit()
    return audit.id, installer.id


async def _make_quote(
    session: Any,
    *,
    audit_id: uuid.UUID,
    installer_id: uuid.UUID,
    uploaded_at: datetime,
    storage_url: str | None = "s3://fake-bucket/quotes/q1.pdf",
) -> InstallerQuote:
    # ``uploaded_at`` has a server_default so we set it manually to age
    # the row backwards in time without waiting for wall-clock.
    quote = InstallerQuote(
        audit_id=audit_id,
        installer_id=installer_id,
        uploaded_at=uploaded_at,
        raw_pdf_storage_url=storage_url,
        raw_pdf_sha256="x" * 64,
    )
    session.add(quote)
    await session.commit()
    return quote


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_storage_key_from_s3_url_strips_bucket() -> None:
    assert storage_key_from_url("s3://my-bucket/audits/abc.pdf") == "audits/abc.pdf"


def test_storage_key_from_s3_url_with_no_key_returns_empty() -> None:
    assert storage_key_from_url("s3://my-bucket") == ""


def test_storage_key_from_unsupported_scheme_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match="unsupported storage URL scheme"):
        storage_key_from_url("https://cdn.example.com/audits/abc.pdf")


# ---------------------------------------------------------------------------
# Happy path — aged row gets purged
# ---------------------------------------------------------------------------


async def test_purge_deletes_object_and_stamps_row(db: Any) -> None:
    storage = FakeStorageProvider()
    await storage.put("quotes/q1.pdf", b"%PDF stale")

    audit_id, installer_id = await _make_audit_and_installer(db)
    now = datetime(2026, 4, 30, 12, tzinfo=UTC)
    aged = now - timedelta(hours=80)
    quote = await _make_quote(
        db,
        audit_id=audit_id,
        installer_id=installer_id,
        uploaded_at=aged,
    )

    result = await purge_expired_pdfs(db, storage, now=now, ttl_hours=72)
    assert result.scanned == 1
    assert result.purged == 1
    assert result.storage_failures == 0

    # Object gone from storage.
    assert await storage.exists("quotes/q1.pdf") is False

    # Row updated.
    async with _db.SessionLocal() as fresh:
        reloaded = await fresh.get(InstallerQuote, quote.id)
        assert reloaded is not None
        assert reloaded.raw_pdf_storage_url is None
        assert reloaded.raw_pdf_purged_at is not None
        # SHA-256 is preserved per the privacy contract — the hash + the
        # extracted JSON are what we keep, just not the raw bytes.
        assert reloaded.raw_pdf_sha256 is not None


# ---------------------------------------------------------------------------
# Idempotency — already-purged rows are skipped
# ---------------------------------------------------------------------------


async def test_purge_skips_rows_already_purged(db: Any) -> None:
    storage = FakeStorageProvider()
    audit_id, installer_id = await _make_audit_and_installer(db)
    now = datetime(2026, 4, 30, 12, tzinfo=UTC)
    aged = now - timedelta(hours=80)

    await _make_quote(
        db,
        audit_id=audit_id,
        installer_id=installer_id,
        uploaded_at=aged,
        storage_url=None,  # already purged
    )

    result = await purge_expired_pdfs(db, storage, now=now, ttl_hours=72)
    assert result == result.__class__(scanned=0, purged=0, storage_failures=0)


async def test_purge_run_twice_is_noop_after_first_sweep(db: Any) -> None:
    storage = FakeStorageProvider()
    await storage.put("quotes/q1.pdf", b"%PDF")
    audit_id, installer_id = await _make_audit_and_installer(db)
    now = datetime(2026, 4, 30, 12, tzinfo=UTC)
    await _make_quote(
        db,
        audit_id=audit_id,
        installer_id=installer_id,
        uploaded_at=now - timedelta(hours=80),
    )

    first = await purge_expired_pdfs(db, storage, now=now, ttl_hours=72)
    second = await purge_expired_pdfs(db, storage, now=now, ttl_hours=72)
    assert first.purged == 1
    assert second.scanned == 0


# ---------------------------------------------------------------------------
# Boundary — rows under the TTL aren't touched
# ---------------------------------------------------------------------------


async def test_purge_leaves_rows_younger_than_ttl_alone(db: Any) -> None:
    storage = FakeStorageProvider()
    await storage.put("quotes/young.pdf", b"%PDF young")
    audit_id, installer_id = await _make_audit_and_installer(db)
    now = datetime(2026, 4, 30, 12, tzinfo=UTC)

    young = now - timedelta(hours=1)
    quote = await _make_quote(
        db,
        audit_id=audit_id,
        installer_id=installer_id,
        uploaded_at=young,
        storage_url="s3://fake-bucket/quotes/young.pdf",
    )

    result = await purge_expired_pdfs(db, storage, now=now, ttl_hours=72)
    assert result.scanned == 0
    assert await storage.exists("quotes/young.pdf") is True

    async with _db.SessionLocal() as fresh:
        reloaded = await fresh.get(InstallerQuote, quote.id)
        assert reloaded is not None
        assert reloaded.raw_pdf_storage_url == "s3://fake-bucket/quotes/young.pdf"
        assert reloaded.raw_pdf_purged_at is None


# ---------------------------------------------------------------------------
# Storage-deletion failure — row left for retry
# ---------------------------------------------------------------------------


async def test_purge_leaves_row_intact_on_storage_failure(db: Any) -> None:
    storage = FakeStorageProvider()
    await storage.put("quotes/flaky.pdf", b"%PDF")

    async def boom(key: str) -> None:
        raise StorageError("simulated R2 outage")

    storage.delete = boom  # type: ignore[method-assign]

    audit_id, installer_id = await _make_audit_and_installer(db)
    now = datetime(2026, 4, 30, 12, tzinfo=UTC)
    quote = await _make_quote(
        db,
        audit_id=audit_id,
        installer_id=installer_id,
        uploaded_at=now - timedelta(hours=80),
        storage_url="s3://fake-bucket/quotes/flaky.pdf",
    )

    result = await purge_expired_pdfs(db, storage, now=now, ttl_hours=72)
    assert result.scanned == 1
    assert result.purged == 0
    assert result.storage_failures == 1

    async with _db.SessionLocal() as fresh:
        reloaded = await fresh.get(InstallerQuote, quote.id)
        # URL stays so the next sweep retries.
        assert reloaded is not None
        assert reloaded.raw_pdf_storage_url == "s3://fake-bucket/quotes/flaky.pdf"
        assert reloaded.raw_pdf_purged_at is None


# ---------------------------------------------------------------------------
# Storage already gone — treated as success
# ---------------------------------------------------------------------------


async def test_purge_treats_missing_object_as_success(db: Any) -> None:
    storage = FakeStorageProvider()
    # Deliberately *don't* put the object — simulates a half-completed
    # prior sweep where the storage delete landed but the row update
    # didn't commit before a crash.

    audit_id, installer_id = await _make_audit_and_installer(db)
    now = datetime(2026, 4, 30, 12, tzinfo=UTC)
    quote = await _make_quote(
        db,
        audit_id=audit_id,
        installer_id=installer_id,
        uploaded_at=now - timedelta(hours=80),
        storage_url="s3://fake-bucket/quotes/missing.pdf",
    )

    result = await purge_expired_pdfs(db, storage, now=now, ttl_hours=72)
    assert result.purged == 1
    assert result.storage_failures == 0

    async with _db.SessionLocal() as fresh:
        reloaded = await fresh.get(InstallerQuote, quote.id)
        assert reloaded is not None
        assert reloaded.raw_pdf_storage_url is None
        assert reloaded.raw_pdf_purged_at is not None


# ---------------------------------------------------------------------------
# Batch size respected
# ---------------------------------------------------------------------------


async def test_purge_respects_batch_size(db: Any) -> None:
    storage = FakeStorageProvider()
    audit_id, installer_id = await _make_audit_and_installer(db)
    now = datetime(2026, 4, 30, 12, tzinfo=UTC)
    aged = now - timedelta(hours=80)
    for i in range(5):
        await storage.put(f"quotes/q{i}.pdf", b"%PDF")
        await _make_quote(
            db,
            audit_id=audit_id,
            installer_id=installer_id,
            uploaded_at=aged,
            storage_url=f"s3://fake-bucket/quotes/q{i}.pdf",
        )

    result = await purge_expired_pdfs(db, storage, now=now, ttl_hours=72, batch_size=2)
    assert result.scanned == 2
    assert result.purged == 2

    # 3 still need purging — next sweep cleans up.
    async with _db.SessionLocal() as fresh:
        remaining = (
            (
                await fresh.execute(
                    select(InstallerQuote).where(InstallerQuote.raw_pdf_storage_url.is_not(None))
                )
            )
            .scalars()
            .all()
        )
        assert len(remaining) == 3


# ---------------------------------------------------------------------------
# Default TTL plumbing
# ---------------------------------------------------------------------------


async def test_purge_default_ttl_comes_from_settings(
    db: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "pdf_storage_ttl_hours", 1, raising=False)
    storage = FakeStorageProvider()
    await storage.put("quotes/q.pdf", b"%PDF")
    audit_id, installer_id = await _make_audit_and_installer(db)
    now = datetime(2026, 4, 30, 12, tzinfo=UTC)
    # 2h old — under the 72h default but over the monkey-patched 1h.
    await _make_quote(
        db,
        audit_id=audit_id,
        installer_id=installer_id,
        uploaded_at=now - timedelta(hours=2),
        storage_url="s3://fake-bucket/quotes/q.pdf",
    )

    result = await purge_expired_pdfs(db, storage, now=now)  # ttl_hours from settings
    assert result.purged == 1
