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
from backend.providers.storage import (
    ObjectNotFoundError,
    StorageError,
    StorageProvider,
)

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

    The storage adapter persists ``s3://<bucket>/<key>`` as the
    canonical handle (see ``backend.providers.storage.s3._object_url``);
    everything between the bucket and the end of the string is the key.
    A URL we don't recognise (legacy https://… style) returns the path
    portion stripped of any leading slash so older formats still purge.
    """
    if url.startswith("s3://"):
        rest = url[len("s3://") :]
        # Drop the bucket prefix; everything after the first ``/`` is the key.
        if "/" in rest:
            return rest.split("/", 1)[1]
        return ""
    # Legacy / pre-S3 URL — fall back to the path portion.
    if "://" in url:
        _, _, after_scheme = url.partition("://")
        if "/" in after_scheme:
            _, _, path = after_scheme.partition("/")
            return path
    return url.lstrip("/")


async def purge_expired_pdfs(
    session: AsyncSession,
    storage: StorageProvider,
    *,
    now: datetime | None = None,
    ttl_hours: int | None = None,
    batch_size: int = 100,
) -> PurgeResult:
    """One sweep: delete every PDF older than the cutoff, return counts.

    The function commits after each successful row so a mid-sweep crash
    leaves a half-purged set behind that the next run cleans up — at
    no point is the ``raw_pdf_purged_at`` stamped without the storage
    delete actually succeeding for that row.

    ``batch_size`` caps how many rows a single invocation processes so
    the sweep is interrupt-friendly under a scheduler that fires it
    every few minutes; the next firing picks up where this one left off.
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
            await storage.delete(key)
        except ObjectNotFoundError:
            # Already gone (prior half-completed sweep). Treat as
            # success — the purge invariant is "no raw PDF + stamped
            # row", which we can still achieve.
            _log.info("pdf_ttl.delete_missing_object_ok", quote_id=str(row.id), key=key)
        except StorageError as exc:
            # Real failure — leave the row's URL intact so the next
            # sweep retries; the audit trail (raw_pdf_purged_at stays
            # null) shows the row hasn't been certified purged yet.
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
        await session.commit()
        purged += 1

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
