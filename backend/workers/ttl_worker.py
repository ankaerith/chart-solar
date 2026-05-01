"""RQ worker entry point for the PDF TTL purge.

Wires the production storage adapter (``S3StorageProvider``) to the
pure ``purge_expired_pdfs`` sweep. The function exists so RQ Scheduler
(or an external cron) can enqueue it on whatever cadence operations
prefers — the recommended start is "every 15 minutes": small enough to
keep the wall-clock between TTL expiry and actual deletion well under
the user-promised 72h, large enough that a sweep that finds zero rows
costs basically nothing.
"""

from __future__ import annotations

import asyncio

import backend.database as _db
from backend.infra.logging import configure_logging, get_logger
from backend.providers.storage.s3 import S3StorageProvider
from backend.services.pdf_ttl_purge import PurgeResult, purge_expired_pdfs

_log = get_logger(__name__)


def run_pdf_ttl_purge_job() -> dict[str, int]:
    """Sync entry point for RQ; returns the sweep counts as JSON."""
    return asyncio.run(_run()).to_dict()


async def _run() -> PurgeResult:
    storage = S3StorageProvider()
    async with _db.SessionLocal() as session:
        return await purge_expired_pdfs(session, storage)


def main() -> None:
    """CLI / cron entry — log on the way in, run, log on the way out."""
    configure_logging("ttl_worker")
    _log.info("pdf_ttl.run_start")
    counts = run_pdf_ttl_purge_job()
    _log.info("pdf_ttl.run_end", **counts)


if __name__ == "__main__":
    main()
