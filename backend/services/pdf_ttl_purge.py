"""Purge raw PDFs from object storage after the configured TTL.

Phase 1 closed decision: 24-72h, default 72h. Background sweep finds
``installer_quotes`` rows where ``raw_pdf_storage_url IS NOT NULL`` and
``uploaded_at`` is older than the cutoff, deletes the object, then
nulls the URL + stamps ``raw_pdf_purged_at``. The SHA-256 hash + the
extracted JSON + the audit's variance output stay — only the raw bytes
go.

Idempotent: a row with a NULL ``raw_pdf_storage_url`` (already purged)
is excluded by the WHERE clause; a missing-object delete in the storage
adapter is caught and treated as a successful purge so a half-failed
prior sweep heals on retry.

Pure-ish: this module takes a session + a ``StorageProvider`` and works
on whichever adapter you hand it — the production worker wires
``S3StorageProvider``, tests wire ``FakeStorageProvider``. No globals,
no env reads outside the TTL default fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.audit_models import InstallerQuote
from backend.infra.logging import get_logger
from backend.providers.storage import StorageError, StorageProvider

_log = get_logger(__name__)


@dataclass(frozen=True)
class PurgeResult:
    """Counts a single sweep produced — for logs + RQ return value."""

    scanned: int
    purged: int
    storage_failures: int

    def to_dict(self) -> dict[str, int]:
        return {
            "scanned": self.scanned,
            "purged": self.purged,
            "storage_failures": self.storage_failures,
        }


def storage_key_from_url(url: str) -> str:
    """Pull the object key out of an ``s3://bucket/key`` reference.

    Inverse of ``backend.providers.storage.s3._object_url`` — every
    URL the adapter mints uses the same scheme, so this is the only
    shape we need to recognise.
    """
    if not url.startswith("s3://"):
        raise ValueError(f"unsupported storage URL scheme: {url!r}")
    rest = url[len("s3://") :]
    if "/" not in rest:
        return ""
    return rest.split("/", 1)[1]


async def purge_expired_pdfs(
    session: AsyncSession,
    storage: StorageProvider,
    *,
    now: datetime | None = None,
    ttl_hours: int | None = None,
    batch_size: int = 100,
) -> PurgeResult:
    """One sweep: delete every PDF older than the cutoff, return counts.

    Storage delete runs per-row (it must — there is no batch S3 op
    in the Protocol), but the DB stamps are committed once at the end
    of the batch so a 100-row sweep is one fsync, not 100. A storage
    failure on row N is logged and that row's URL stays intact for
    the next sweep to retry; the rest of the batch still commits.

    ``batch_size`` caps how many rows a single invocation processes so
    the sweep is interrupt-friendly under a scheduler that fires it
    every few minutes.
    """
    cutoff_now = now or datetime.now(UTC)
    ttl = timedelta(hours=ttl_hours if ttl_hours is not None else settings.pdf_storage_ttl_hours)
    cutoff = cutoff_now - ttl

    stmt = (
        select(InstallerQuote)
        .where(
            InstallerQuote.raw_pdf_storage_url.is_not(None),
            InstallerQuote.uploaded_at < cutoff,
        )
        .limit(batch_size)
    )
    rows = (await session.execute(stmt)).scalars().all()

    purged = 0
    storage_failures = 0
    for row in rows:
        url = row.raw_pdf_storage_url
        if url is None:
            continue
        key = storage_key_from_url(url)
        try:
            # Delete is idempotent in the Protocol — missing objects
            # complete cleanly without raising, so a half-completed
            # prior sweep heals on retry.
            await storage.delete(key)
        except StorageError as exc:
            _log.warning(
                "pdf_ttl.storage_delete_failed",
                quote_id=str(row.id),
                key=key,
                error=str(exc),
            )
            storage_failures += 1
            continue

        row.raw_pdf_storage_url = None
        row.raw_pdf_purged_at = cutoff_now
        purged += 1

    if purged:
        await session.commit()

    result = PurgeResult(
        scanned=len(rows),
        purged=purged,
        storage_failures=storage_failures,
    )
    if result.scanned > 0:
        _log.info(
            "pdf_ttl.sweep_complete",
            scanned=result.scanned,
            purged=result.purged,
            storage_failures=result.storage_failures,
            ttl_hours=ttl.total_seconds() / 3600,
        )
    return result


__all__ = [
    "PurgeResult",
    "purge_expired_pdfs",
    "storage_key_from_url",
]
