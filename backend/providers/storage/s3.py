"""S3-compatible adapter (R2 / S3 / GCS-interop / MinIO) via aioboto3.

Endpoint selection is config-driven — the same code talks to:

* AWS S3 (no ``s3_endpoint_url``);
* Cloudflare R2 (``s3_endpoint_url=https://<acct>.r2.cloudflarestorage.com``);
* Google Cloud Storage interop (``s3_endpoint_url=https://storage.googleapis.com``);
* MinIO in local dev (``s3_endpoint_url=http://minio:9000``).

Encrypt-at-rest is on by default (``ServerSideEncryption='AES256'`` —
SSE-S3). Buckets are assumed private; nothing in this adapter sets a
public ACL. Both expectations are documented in the
:class:`backend.providers.storage.StorageProvider` Protocol.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.config import require, settings
from backend.providers.storage import (
    ObjectNotFoundError,
    StorageError,
    StoredObject,
)


def _client_kwargs() -> dict[str, Any]:
    """Build the kwargs passed to ``aioboto3.Session().client('s3', ...)``.

    Pulled out so the adapter and tests can both reach for the same
    settings-derived shape without duplicating env-var names.
    """
    kwargs: dict[str, Any] = {
        "region_name": settings.s3_region,
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    if settings.s3_access_key_id and settings.s3_secret_access_key:
        kwargs["aws_access_key_id"] = settings.s3_access_key_id
        kwargs["aws_secret_access_key"] = settings.s3_secret_access_key
    return kwargs


def _object_url(bucket: str, key: str) -> str:
    """The canonical reference we persist with audit rows.

    The format ``s3://<bucket>/<key>`` round-trips cleanly through
    ``delete``; the actual upstream is rebuilt from settings, not
    parsed out of this string. Avoids a brittle dependency on whichever
    S3-compatible host the deployment happens to be using today.
    """
    return f"s3://{bucket}/{key}"


class S3StorageProvider:
    """``StorageProvider`` against an S3-compatible bucket.

    The bucket name is read from ``settings.s3_bucket`` at construction
    time and is required — the adapter refuses to start without one,
    rather than failing at the first ``put`` with an opaque botocore
    error. A ``ServerSideEncryption='AES256'`` header is added to every
    upload so encrypt-at-rest is the default; callers can override via
    ``extra_put_args`` only when the bucket is configured for SSE-KMS.
    """

    name = "s3"

    def __init__(
        self,
        *,
        bucket: str | None = None,
        extra_put_args: dict[str, Any] | None = None,
    ) -> None:
        # ``aioboto3`` is imported lazily so ``import backend.providers``
        # at startup doesn't pay the boto3 + botocore import cost on
        # services that never touch storage.
        import aioboto3  # noqa: PLC0415

        self._bucket = require(bucket or settings.s3_bucket, "S3_BUCKET")
        self._session = aioboto3.Session()
        self._extra_put_args = extra_put_args or {}

    @property
    def bucket(self) -> str:
        return self._bucket

    def _client(self) -> Any:
        """Return an ``async with`` context manager for an S3 client.

        Each call creates a fresh client. ``aioboto3``'s session caches
        the underlying httpx pool, so the construction cost is small;
        per-request clients keep us safe across event loops in test runs.
        """
        return self._session.client("s3", **_client_kwargs())

    async def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        put_args: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
            # SSE-S3. Override per-instance via ``extra_put_args`` for
            # SSE-KMS deployments; the Protocol forbids unencrypted writes.
            "ServerSideEncryption": "AES256",
            **self._extra_put_args,
        }
        if metadata:
            put_args["Metadata"] = metadata

        async with self._client() as client:
            try:
                await client.put_object(**put_args)
            except Exception as exc:  # noqa: BLE001 — wrap in StorageError
                raise StorageError(f"put failed for key={key!r}: {exc!r}") from exc

        return StoredObject(
            key=key,
            url=_object_url(self._bucket, key),
            size_bytes=len(data),
            content_type=content_type,
            metadata=dict(metadata or {}),
        )

    async def get(self, key: str) -> bytes:
        async with self._client() as client:
            try:
                resp = await client.get_object(Bucket=self._bucket, Key=key)
            except client.exceptions.NoSuchKey as exc:
                raise ObjectNotFoundError(key) from exc
            except Exception as exc:  # noqa: BLE001
                raise StorageError(f"get failed for key={key!r}: {exc!r}") from exc
            body = resp["Body"]
            return await body.read()  # type: ignore[no-any-return]

    async def delete(self, key: str) -> None:
        async with self._client() as client:
            # S3 ``DeleteObject`` is idempotent and returns 204 even when
            # the key doesn't exist. Probe with ``head_object`` first so
            # callers that want missing-key signalling get it via
            # :class:`ObjectNotFoundError`; the TTL purge wraps + ignores.
            try:
                await client.head_object(Bucket=self._bucket, Key=key)
            except client.exceptions.ClientError as exc:
                if _is_not_found(exc):
                    raise ObjectNotFoundError(key) from exc
                raise StorageError(f"delete probe failed for key={key!r}: {exc!r}") from exc
            try:
                await client.delete_object(Bucket=self._bucket, Key=key)
            except Exception as exc:  # noqa: BLE001
                raise StorageError(f"delete failed for key={key!r}: {exc!r}") from exc

    async def exists(self, key: str) -> bool:
        async with self._client() as client:
            try:
                await client.head_object(Bucket=self._bucket, Key=key)
            except client.exceptions.ClientError as exc:
                if _is_not_found(exc):
                    return False
                raise StorageError(f"exists probe failed for key={key!r}: {exc!r}") from exc
            return True

    async def list(
        self,
        *,
        prefix: str = "",
        limit: int = 1000,
    ) -> list[StoredObject]:
        results: list[StoredObject] = []
        async with self._client() as client:
            try:
                resp = await client.list_objects_v2(
                    Bucket=self._bucket,
                    Prefix=prefix,
                    MaxKeys=limit,
                )
            except Exception as exc:  # noqa: BLE001
                raise StorageError(f"list failed for prefix={prefix!r}: {exc!r}") from exc

        for entry in resp.get("Contents", []):
            key = entry["Key"]
            last_modified = entry.get("LastModified")
            results.append(
                StoredObject(
                    key=key,
                    url=_object_url(self._bucket, key),
                    size_bytes=entry.get("Size"),
                    last_modified=_as_datetime(last_modified),
                )
            )
        return results


def _is_not_found(exc: Any) -> bool:
    """S3 surfaces missing keys as ``404`` / ``NoSuchKey`` / ``Not Found``.

    ``head_object`` raises a generic ``ClientError`` with a 404 status;
    ``get_object`` raises ``NoSuchKey``. We normalise both to the
    Protocol's :class:`ObjectNotFoundError` so callers don't have to
    care about the boto3 surface.
    """
    response = getattr(exc, "response", None) or {}
    error = response.get("Error") or {}
    code = str(error.get("Code", ""))
    if code in {"404", "NoSuchKey", "NotFound"}:
        return True
    status = (response.get("ResponseMetadata") or {}).get("HTTPStatusCode")
    return status == 404


def _as_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    return None


__all__ = ["S3StorageProvider"]
