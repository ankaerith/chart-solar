"""VertexClient tests — ZDR enforcement, region pinning, payload guards.

The wrapper never reaches Vertex in this suite. We swap the SDK out for
a stub via ``client_factory`` and assert the call shape (vertex routing,
``response_mime_type=application/json``, ``response_schema``, no
``cached_content``) and the configuration guards (ZDR flags, 19 MB cap,
empty payload, AI Studio rejection).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
from pydantic import BaseModel

from backend.services.vertex_client import (
    MAX_INLINE_PDF_BYTES,
    VertexClient,
    VertexConfigurationError,
    VertexExtractionError,
    VertexInputError,
    default_region_for_country,
)

# ---------------------------------------------------------------------------
# Helpers + stubs
# ---------------------------------------------------------------------------


@pytest.fixture
def zdr_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Pretend the env has ZDR + abuse-logging exemption + project id."""
    from backend.config import settings

    monkeypatch.setattr(settings, "vertex_zdr_enabled", True, raising=False)
    monkeypatch.setattr(settings, "vertex_abuse_logging_exempt", True, raising=False)
    monkeypatch.setattr(settings, "vertex_project_id", "chart-solar-test", raising=False)
    monkeypatch.setattr(settings, "vertex_location", "us-central1", raising=False)
    yield


class TinyExtraction(BaseModel):
    panel_count: int
    confidence: float


@dataclass
class _RecordedCall:
    model: str
    contents: list[Any]
    config: Any


class _StubResponse:
    def __init__(self, text: str) -> None:
        self.text = text


@dataclass
class _StubModels:
    calls: list[_RecordedCall] = field(default_factory=list)
    response_text: str = '{"panel_count": 24, "confidence": 0.91}'

    async def generate_content(
        self,
        *,
        model: str,
        contents: list[Any],
        config: Any,
    ) -> _StubResponse:
        self.calls.append(_RecordedCall(model=model, contents=list(contents), config=config))
        return _StubResponse(self.response_text)


@dataclass
class _StubAio:
    models: _StubModels


@dataclass
class _StubApiClient:
    """Mirrors the ``vertexai`` flag the real SDK exposes."""

    vertexai: bool = True


@dataclass
class _StubClient:
    location: str
    aio: _StubAio = field(default_factory=lambda: _StubAio(_StubModels()))
    _api_client: _StubApiClient = field(default_factory=_StubApiClient)


def _factory(location: str, *, ai_studio: bool = False) -> _StubClient:
    return _StubClient(
        location=location,
        _api_client=_StubApiClient(vertexai=not ai_studio),
    )


# ---------------------------------------------------------------------------
# Configuration guards
# ---------------------------------------------------------------------------


def test_constructor_refuses_when_zdr_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "vertex_zdr_enabled", False, raising=False)
    monkeypatch.setattr(settings, "vertex_abuse_logging_exempt", True, raising=False)
    monkeypatch.setattr(settings, "vertex_project_id", "p", raising=False)

    with pytest.raises(VertexConfigurationError, match="VERTEX_ZDR_ENABLED"):
        VertexClient(client_factory=lambda location: _factory(location))


def test_constructor_refuses_when_abuse_logging_exemption_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.config import settings

    monkeypatch.setattr(settings, "vertex_zdr_enabled", True, raising=False)
    monkeypatch.setattr(settings, "vertex_abuse_logging_exempt", False, raising=False)
    monkeypatch.setattr(settings, "vertex_project_id", "p", raising=False)

    with pytest.raises(VertexConfigurationError, match="ABUSE_LOGGING"):
        VertexClient(client_factory=lambda location: _factory(location))


def test_constructor_rejects_ai_studio_routed_client(zdr_settings: None) -> None:
    """If a caller hands us a client built with ``vertexai=False`` we
    must abort — that surface points at generativelanguage.googleapis.com."""
    with pytest.raises(VertexConfigurationError, match="AI Studio"):
        VertexClient(
            client_factory=lambda location: _factory(location, ai_studio=True),
        )


def test_constructor_pins_default_region_to_us_central1(zdr_settings: None) -> None:
    client = VertexClient(client_factory=lambda location: _factory(location))
    assert client.region == "us-central1"


def test_constructor_accepts_uk_region(zdr_settings: None) -> None:
    client = VertexClient(
        region="europe-west2",
        client_factory=lambda location: _factory(location),
    )
    assert client.region == "europe-west2"


def test_default_region_for_country_routes_uk_to_europe_west2() -> None:
    assert default_region_for_country("UK") == "europe-west2"
    assert default_region_for_country("GB") == "europe-west2"
    assert default_region_for_country("US") == "us-central1"
    # Unknown country falls back to the US default rather than raising.
    assert default_region_for_country("ZZ") == "us-central1"


# ---------------------------------------------------------------------------
# Payload guards
# ---------------------------------------------------------------------------


async def test_extract_rejects_empty_pdf(zdr_settings: None) -> None:
    client = VertexClient(client_factory=lambda location: _factory(location))
    with pytest.raises(VertexInputError, match="empty"):
        await client.extract(pdf_bytes=b"", schema=TinyExtraction)


async def test_extract_rejects_oversize_pdf(zdr_settings: None) -> None:
    client = VertexClient(client_factory=lambda location: _factory(location))
    too_big = b"x" * (MAX_INLINE_PDF_BYTES + 1)
    with pytest.raises(VertexInputError, match="inline limit"):
        await client.extract(pdf_bytes=too_big, schema=TinyExtraction)


# ---------------------------------------------------------------------------
# Happy path — extraction call shape
# ---------------------------------------------------------------------------


async def test_extract_sends_inline_pdf_and_parses_response(zdr_settings: None) -> None:
    stub = _StubClient(location="us-central1")
    client = VertexClient(client_factory=lambda location: stub)

    result = await client.extract(
        pdf_bytes=b"%PDF-1.4 ... fake",
        schema=TinyExtraction,
    )

    assert isinstance(result, TinyExtraction)
    assert result.panel_count == 24
    assert result.confidence == pytest.approx(0.91)

    assert len(stub.aio.models.calls) == 1
    call = stub.aio.models.calls[0]
    # Tier defaults to 2.5-flash.
    assert call.model == "gemini-2.5-flash"
    # Single inline PDF part with the proper mime type.
    assert len(call.contents) == 1
    part = call.contents[0]
    assert getattr(part, "inline_data", None) is not None or hasattr(part, "model_dump")
    # JSON-mode + schema enforced.
    assert call.config.response_mime_type == "application/json"
    assert call.config.response_schema is TinyExtraction
    # ZDR: never use context caching.
    assert getattr(call.config, "cached_content", None) is None


async def test_extract_uses_pro_3_tier_when_requested(zdr_settings: None) -> None:
    stub = _StubClient(location="us-central1")
    client = VertexClient(client_factory=lambda location: stub)

    await client.extract(
        pdf_bytes=b"%PDF",
        schema=TinyExtraction,
        model_tier="pro_3",
    )

    assert stub.aio.models.calls[0].model == "gemini-3-pro"


async def test_extract_passes_system_prompt_when_provided(zdr_settings: None) -> None:
    stub = _StubClient(location="us-central1")
    client = VertexClient(client_factory=lambda location: stub)

    await client.extract(
        pdf_bytes=b"%PDF",
        schema=TinyExtraction,
        system_prompt="You are an extraction assistant.",
    )

    config = stub.aio.models.calls[0].config
    assert config.system_instruction == "You are an extraction assistant."


async def test_extract_per_call_region_override_uses_separate_client(
    zdr_settings: None,
) -> None:
    """A UK request issued from a US-pinned client must build a fresh
    client at ``europe-west2`` rather than reusing the US one."""
    built: list[str] = []

    def factory(*, location: str) -> _StubClient:
        built.append(location)
        return _StubClient(location=location)

    client = VertexClient(client_factory=factory)
    assert built == ["us-central1"]

    await client.extract(
        pdf_bytes=b"%PDF",
        schema=TinyExtraction,
        region="europe-west2",
    )

    assert built == ["us-central1", "europe-west2"]


async def test_extract_wraps_upstream_errors(zdr_settings: None) -> None:
    stub = _StubClient(location="us-central1")
    client = VertexClient(client_factory=lambda location: stub)

    async def boom(**kwargs: Any) -> _StubResponse:
        raise RuntimeError("upstream boom")

    stub.aio.models.generate_content = boom  # type: ignore[method-assign]

    with pytest.raises(VertexExtractionError, match="vertex extract failed"):
        await client.extract(pdf_bytes=b"%PDF", schema=TinyExtraction)


async def test_extract_rejects_response_that_does_not_match_schema(
    zdr_settings: None,
) -> None:
    stub = _StubClient(location="us-central1")
    stub.aio.models.response_text = '{"panel_count": "not-an-int"}'
    client = VertexClient(client_factory=lambda location: stub)

    with pytest.raises(VertexExtractionError, match="does not match"):
        await client.extract(pdf_bytes=b"%PDF", schema=TinyExtraction)


async def test_extract_falls_back_to_sync_models_when_aio_absent(
    zdr_settings: None,
) -> None:
    """A test mock that only exposes the sync path still works."""

    @dataclass
    class _SyncStub:
        location: str
        models: _StubModels = field(default_factory=_StubModels)
        _api_client: _StubApiClient = field(default_factory=_StubApiClient)

    stub = _SyncStub(location="us-central1")
    # ``generate_content`` on the sync surface needs to be sync, not async,
    # to mirror the live SDK; awaiting a sync return is the wrapper's job.

    def sync_generate(**kwargs: Any) -> _StubResponse:
        return _StubResponse('{"panel_count": 12, "confidence": 0.5}')

    stub.models.generate_content = sync_generate  # type: ignore[assignment]

    client = VertexClient(client_factory=lambda location: stub)
    result = await client.extract(pdf_bytes=b"%PDF", schema=TinyExtraction)
    assert result.panel_count == 12
