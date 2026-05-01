"""StorageProvider port — S3-compatible object storage.

PDF uploads, methodology exports, and irradiance snapshots all live in
S3-compatible storage so the same adapter code works against R2, S3,
GCS (interop), and MinIO (local dev) — only the ``s3_endpoint_url`` and
credentials change. Per the project stack rules, no provider-proprietary
features sit in the hot path.

The Protocol is intentionally narrow: ``put`` / ``get`` / ``delete`` /
``exists`` / ``list``. The 24-72h PDF TTL purge (chart-solar-ebo)
composes ``list`` + ``delete``; nothing here knows about TTLs because
the policy lives one layer up. Encrypt-at-rest is the adapter's job —
the Protocol carries no public/ACL knobs because the only supported
configuration is **private buckets, encrypted at rest** (LEGAL § F1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable


class StorageError(RuntimeError):
    """Raised when an upstream object-storage operation fails."""


class ObjectNotFoundError(StorageError):
    """Raised when ``get`` / ``delete`` target a key that doesn't exist."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"object not found: {key!r}")


@dataclass(frozen=True)
class StoredObject:
    """Handle returned by ``put`` and ``list``.

    ``url`` is the canonical reference persisted by callers (e.g.
    ``installer_quotes.raw_pdf_storage_url``); the format is
    ``<provider-scheme>://<bucket>/<key>`` so the same string round-trips
    through ``delete`` regardless of which S3-compatible upstream
    actually backs the bucket. ``last_modified`` and ``size_bytes`` are
    optional because ``put`` populates them only when the upstream
    returns them in the response (S3 always does; some emulators don't).
    """

    key: str
    url: str
    size_bytes: int | None = None
    last_modified: datetime | None = None
    content_type: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class StorageProvider(Protocol):
    """Put/get/delete/exists/list against an S3-compatible bucket.

    Implementations MUST:

    * write objects encrypted at rest (SSE-S3 or stronger);
    * never set a public ACL — buckets are private and access is
      brokered through signed URLs at a higher layer when needed;
    * raise :class:`ObjectNotFoundError` (a :class:`StorageError`
      subclass) when a key is missing on ``get`` / ``delete``;
    * be safe to call concurrently from multiple coroutines on the
      same adapter instance.
    """

    name: str

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        """Upload ``data`` under ``key``; overwrite if it already exists."""
        ...

    async def get(self, key: str) -> bytes:
        """Fetch raw bytes; raise :class:`ObjectNotFoundError` if missing."""
        ...

    async def delete(self, key: str) -> None:
        """Remove ``key``; raise :class:`ObjectNotFoundError` if missing.

        The PDF TTL purge (chart-solar-ebo) treats a successful delete
        and a missing-key delete as equivalent — it catches
        :class:`ObjectNotFoundError` and continues. Other callers can
        decide for themselves.
        """
        ...

    async def exists(self, key: str) -> bool:
        """Return whether ``key`` is present without fetching the body."""
        ...

    async def list(
        self,
        *,
        prefix: str = "",
        limit: int = 1000,
    ) -> list[StoredObject]:
        """Return up to ``limit`` objects whose key starts with ``prefix``.

        Pagination is intentionally absent in v1 — the only caller is
        the TTL purge job, which works one bounded batch at a time. If
        a bigger sweep is needed, add cursor-based pagination here and
        update both adapters in lockstep.
        """
        ...


__all__ = [
    "ObjectNotFoundError",
    "StorageError",
    "StorageProvider",
    "StoredObject",
]
