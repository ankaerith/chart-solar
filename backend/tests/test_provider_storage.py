"""StorageProvider Protocol + Fake + S3 adapter tests.

The fake test suite (``test_fake_*``) is the Protocol contract — every
storage adapter must pass it. The S3-adapter tests stub aioboto3's
client so we exercise the put/head/get/delete/list call shapes,
SSE-AES256 default, and the ``ObjectNotFoundError`` translation
without touching the network.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from backend.providers.fake import FakeStorageProvider
from backend.providers.storage import (
    ObjectNotFoundError,
    StorageError,
    StorageProvider,
    StoredObject,
)

# ---------------------------------------------------------------------------
# Protocol conformance — fake
# ---------------------------------------------------------------------------


def test_fake_satisfies_protocol() -> None:
    p: StorageProvider = FakeStorageProvider()
    assert isinstance(p, StorageProvider)
    assert p.name == "fake"


async def test_fake_put_then_get_round_trips_bytes() -> None:
    p = FakeStorageProvider()
    handle = await p.put(
        "audits/abc/proposal.pdf",
        b"%PDF-1.4 ... fake",
        content_type="application/pdf",
        metadata={"audit_id": "abc"},
    )
    assert isinstance(handle, StoredObject)
    assert handle.key == "audits/abc/proposal.pdf"
    assert handle.url == "s3://fake-bucket/audits/abc/proposal.pdf"
    assert handle.size_bytes == len(b"%PDF-1.4 ... fake")
    assert handle.content_type == "application/pdf"
    assert handle.metadata == {"audit_id": "abc"}

    body = await p.get("audits/abc/proposal.pdf")
    assert body == b"%PDF-1.4 ... fake"


async def test_fake_get_missing_raises_object_not_found() -> None:
    p = FakeStorageProvider()
    with pytest.raises(ObjectNotFoundError) as info:
        await p.get("nope")
    assert info.value.key == "nope"


async def test_fake_delete_missing_is_idempotent() -> None:
    p = FakeStorageProvider()
    # Idempotent contract — must not raise.
    await p.delete("nope")
    assert await p.exists("nope") is False


async def test_fake_exists_distinguishes_present_from_absent() -> None:
    p = FakeStorageProvider()
    await p.put("k", b"x")
    assert await p.exists("k") is True
    assert await p.exists("missing") is False


async def test_fake_delete_removes_object() -> None:
    p = FakeStorageProvider()
    await p.put("k", b"x")
    await p.delete("k")
    assert await p.exists("k") is False


async def test_fake_list_returns_prefix_match_in_lexicographic_order() -> None:
    p = FakeStorageProvider()
    await p.put("audits/b.pdf", b"b")
    await p.put("audits/a.pdf", b"a")
    await p.put("snapshots/x.json", b"x")

    audits = await p.list(prefix="audits/")
    assert [o.key for o in audits] == ["audits/a.pdf", "audits/b.pdf"]

    everything = await p.list()
    assert [o.key for o in everything] == ["audits/a.pdf", "audits/b.pdf", "snapshots/x.json"]


async def test_fake_list_respects_limit() -> None:
    p = FakeStorageProvider()
    for i in range(5):
        await p.put(f"k{i}", b"x")
    assert len(await p.list(limit=2)) == 2


async def test_fake_clock_drives_last_modified_for_ttl_purge() -> None:
    """The PDF TTL purge ages objects by ``last_modified``; a stub clock
    lets the purge test advance time deterministically."""
    fixed = datetime(2026, 4, 30, 12, tzinfo=UTC)
    later = fixed + timedelta(hours=73)
    times = iter([fixed, later])
    p = FakeStorageProvider(clock=lambda: next(times))

    older = await p.put("old", b"x")
    newer = await p.put("new", b"y")
    assert older.last_modified == fixed
    assert newer.last_modified == later


# ---------------------------------------------------------------------------
# S3 adapter — stubbed aioboto3
# ---------------------------------------------------------------------------


# Mirrors boto3's exception surface; names are dictated by the upstream
# API so the adapter's ``client.exceptions.NoSuchKey`` lookup works.
class _StubExceptions:
    class NoSuchKey(Exception):  # noqa: N818
        ...

    class ClientError(Exception):  # noqa: N818
        def __init__(self, response: dict[str, Any]) -> None:
            self.response = response
            super().__init__(str(response))


class _StubBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def read(self) -> bytes:
        return self._data


class _StubS3Client:
    """Records every call + lets a test pre-seed responses / errors."""

    def __init__(self) -> None:
        self.exceptions = _StubExceptions()
        self.put_calls: list[dict[str, Any]] = []
        self.head_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []
        self.delete_calls: list[dict[str, Any]] = []
        self.list_calls: list[dict[str, Any]] = []
        self.objects: dict[str, bytes] = {}
        self.list_response: dict[str, Any] = {"Contents": []}

    async def __aenter__(self) -> _StubS3Client:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.put_calls.append(kwargs)
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {"ETag": '"abc"'}

    async def head_object(self, **kwargs: Any) -> dict[str, Any]:
        self.head_calls.append(kwargs)
        key = kwargs["Key"]
        if key not in self.objects:
            raise self.exceptions.ClientError(
                {"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}}
            )
        return {"ContentLength": len(self.objects[key])}

    async def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.get_calls.append(kwargs)
        key = kwargs["Key"]
        if key not in self.objects:
            raise self.exceptions.NoSuchKey("missing")
        return {"Body": _StubBody(self.objects[key])}

    async def delete_object(self, **kwargs: Any) -> dict[str, Any]:
        self.delete_calls.append(kwargs)
        self.objects.pop(kwargs["Key"], None)
        return {}

    async def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        self.list_calls.append(kwargs)
        return self.list_response


@pytest.fixture
def s3_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend the env has S3 credentials so the adapter constructs."""
    from backend.config import settings

    monkeypatch.setattr(settings, "s3_bucket", "test-bucket", raising=False)
    monkeypatch.setattr(settings, "s3_region", "us-east-1", raising=False)
    monkeypatch.setattr(settings, "s3_endpoint_url", None, raising=False)
    monkeypatch.setattr(settings, "s3_access_key_id", "AKIA-TEST", raising=False)
    monkeypatch.setattr(settings, "s3_secret_access_key", "secret-test", raising=False)


def _install_stub_client(
    monkeypatch: pytest.MonkeyPatch,
) -> _StubS3Client:
    """Replace ``S3StorageProvider._client`` with one that returns a stub."""
    from backend.providers.storage import s3 as s3_mod

    # Construct a single shared stub the test can inspect after the call.
    client = _StubS3Client()

    def fake_client(self: s3_mod.S3StorageProvider) -> _StubS3Client:
        return client

    monkeypatch.setattr(s3_mod.S3StorageProvider, "_client", fake_client)
    return client


def test_s3_provider_requires_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.config import settings
    from backend.providers.storage.s3 import S3StorageProvider

    monkeypatch.setattr(settings, "s3_bucket", None, raising=False)
    with pytest.raises(RuntimeError, match="S3_BUCKET"):
        S3StorageProvider()


async def test_s3_put_uses_sse_aes256_and_records_metadata(
    s3_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.providers.storage.s3 import S3StorageProvider

    stub = _install_stub_client(monkeypatch)
    p = S3StorageProvider()

    handle = await p.put(
        "audits/abc/proposal.pdf",
        b"%PDF",
        content_type="application/pdf",
        metadata={"audit_id": "abc"},
    )

    assert len(stub.put_calls) == 1
    call = stub.put_calls[0]
    assert call["Bucket"] == "test-bucket"
    assert call["Key"] == "audits/abc/proposal.pdf"
    assert call["Body"] == b"%PDF"
    assert call["ContentType"] == "application/pdf"
    # Encrypt-at-rest is the default — AES256 (SSE-S3).
    assert call["ServerSideEncryption"] == "AES256"
    assert call["Metadata"] == {"audit_id": "abc"}

    assert handle.url == "s3://test-bucket/audits/abc/proposal.pdf"
    assert handle.size_bytes == len(b"%PDF")
    assert handle.content_type == "application/pdf"


async def test_s3_get_translates_no_such_key_to_object_not_found(
    s3_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.providers.storage.s3 import S3StorageProvider

    _install_stub_client(monkeypatch)
    p = S3StorageProvider()
    with pytest.raises(ObjectNotFoundError):
        await p.get("missing")


async def test_s3_delete_is_one_round_trip_and_idempotent_on_missing(
    s3_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.providers.storage.s3 import S3StorageProvider

    stub = _install_stub_client(monkeypatch)
    p = S3StorageProvider()

    # S3 DeleteObject is itself idempotent; we don't probe with head.
    await p.delete("missing")
    assert stub.head_calls == []
    assert stub.delete_calls == [{"Bucket": "test-bucket", "Key": "missing"}]


async def test_s3_delete_removes_existing_object(
    s3_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.providers.storage.s3 import S3StorageProvider

    stub = _install_stub_client(monkeypatch)
    p = S3StorageProvider()
    await p.put("k", b"x", content_type="text/plain")
    await p.delete("k")
    assert stub.delete_calls == [{"Bucket": "test-bucket", "Key": "k"}]


async def test_s3_exists_returns_false_for_missing(
    s3_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.providers.storage.s3 import S3StorageProvider

    _install_stub_client(monkeypatch)
    p = S3StorageProvider()
    assert await p.exists("missing") is False


async def test_s3_exists_returns_true_for_present(
    s3_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.providers.storage.s3 import S3StorageProvider

    _install_stub_client(monkeypatch)
    p = S3StorageProvider()
    await p.put("k", b"x")
    assert await p.exists("k") is True


async def test_s3_list_passes_prefix_and_limit(
    s3_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.providers.storage.s3 import S3StorageProvider

    stub = _install_stub_client(monkeypatch)
    last_modified = datetime(2026, 4, 30, 12, tzinfo=UTC)
    stub.list_response = {
        "Contents": [
            {"Key": "audits/a.pdf", "Size": 10, "LastModified": last_modified},
            {"Key": "audits/b.pdf", "Size": 20, "LastModified": last_modified},
        ]
    }
    p = S3StorageProvider()

    out = await p.list(prefix="audits/", limit=50)
    assert stub.list_calls == [{"Bucket": "test-bucket", "Prefix": "audits/", "MaxKeys": 50}]
    assert [o.key for o in out] == ["audits/a.pdf", "audits/b.pdf"]
    assert out[0].size_bytes == 10
    assert out[0].last_modified == last_modified
    assert out[0].url == "s3://test-bucket/audits/a.pdf"


async def test_s3_put_failure_wraps_in_storage_error(
    s3_settings: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.providers.storage.s3 import S3StorageProvider

    stub = _install_stub_client(monkeypatch)

    async def boom(**kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("upstream boom")

    stub.put_object = boom  # type: ignore[method-assign]
    p = S3StorageProvider()
    with pytest.raises(StorageError, match="put failed"):
        await p.put("k", b"x")
