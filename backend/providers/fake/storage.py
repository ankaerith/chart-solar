"""In-memory ``StorageProvider`` for tests + offline dev.

Backed by a per-instance ``dict[str, _Record]``. No persistence, no
locks (single-process tests don't need them), no SSE bookkeeping —
encrypt-at-rest is the live adapter's contract, not something the fake
needs to simulate. Behaviourally faithful where it matters: missing
keys raise :class:`ObjectNotFoundError`, prefix listing returns objects
in lexicographic order, ``last_modified`` is populated on every put so
the TTL purge can age objects out under a controllable clock.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from backend.infra.util import utc_now
from backend.providers.storage import (
    ObjectNotFoundError,
    StoredObject,
)


@dataclass
class _Record:
    data: bytes
    content_type: str
    metadata: dict[str, str]
    last_modified: datetime


class FakeStorageProvider:
    """In-memory ``StorageProvider``.

    ``clock`` is injectable so the TTL purge test can advance time
    without ``time.sleep``. Defaults to wall clock.
    """

    name = "fake"

    def __init__(
        self,
        *,
        bucket: str = "fake-bucket",
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._bucket = bucket
        self._objects: dict[str, _Record] = {}
        self._clock = clock

    @property
    def bucket(self) -> str:
        return self._bucket

    def _url(self, key: str) -> str:
        return f"s3://{self._bucket}/{key}"

    def _stored(self, key: str, record: _Record) -> StoredObject:
        return StoredObject(
            key=key,
            url=self._url(key),
            size_bytes=len(record.data),
            last_modified=record.last_modified,
            content_type=record.content_type,
            metadata=dict(record.metadata),
        )

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        record = _Record(
            data=bytes(data),
            content_type=content_type,
            metadata=dict(metadata or {}),
            last_modified=self._clock(),
        )
        self._objects[key] = record
        return self._stored(key, record)

    async def get(self, key: str) -> bytes:
        record = self._objects.get(key)
        if record is None:
            raise ObjectNotFoundError(key)
        return record.data

    async def delete(self, key: str) -> None:
        # Idempotent: missing keys are not an error (matches S3 DeleteObject).
        self._objects.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._objects

    async def list(
        self,
        *,
        prefix: str = "",
        limit: int = 1000,
    ) -> list[StoredObject]:
        matched_keys = sorted(k for k in self._objects if k.startswith(prefix))
        return [self._stored(k, self._objects[k]) for k in matched_keys[:limit]]


__all__ = ["FakeStorageProvider"]
