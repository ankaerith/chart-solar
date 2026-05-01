"""Vertex AI Gemini wrapper for proposal extraction.

Single-vendor by Phase 1 closed decision: Vertex AI only. The wrapper
exists so the rest of the audit pipeline (orchestrator, escalation
policy, prompts) talks to a typed ``extract`` method instead of
googling around the SDK every time.

Hard constraints baked into this module — every one is a "production
won't start" check, not a soft warning:

* **Vertex routing only.** ``google.genai.Client`` is built with
  ``vertexai=True``; the AI Studio surface (``api_key`` route into
  ``generativelanguage.googleapis.com``) is never reachable from this
  module. A defensive guard rejects ``api_key=...`` callers.
* **Region pinning.** UK traffic must hit ``europe-west2``; US traffic
  picks between ``us-central1`` and ``us-east4``. Per-call override
  beats the construction-time default; both go through
  :class:`Region` so a typo at the call site fails type-check.
* **ZDR mandatory.** Both ``vertex_zdr_enabled`` and
  ``vertex_abuse_logging_exempt`` must be true at construction; the
  wrapper refuses to instantiate otherwise. Inside ``extract`` we never
  set ``cached_content`` — context caching is a ZDR violation per
  Vertex docs.
* **Inline-data only, ≤ 19MB.** PDFs go on the wire as ``inline_data``;
  we never call the Files API (which keeps a copy for 48h, breaking
  ZDR). The 19 MB cap leaves headroom under the 20 MB inline limit so
  base64 encoding doesn't push us over.

Mock-friendly: tests inject ``client_factory`` to swap the real
``genai.Client`` for a stub. The default factory is the only place the
SDK is constructed.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, TypeVar

from pydantic import BaseModel

from backend.config import require, settings
from backend.infra.logging import get_logger

#: One of the regions the audit pipeline can pin a request to. The
#: literal is exhaustive on purpose — adding a region requires a code
#: review (and a corresponding ZDR-attested project in GCP).
Region = Literal["us-central1", "us-east4", "europe-west2"]

#: Tier names used by the escalation policy
#: (chart-solar-1yz). The wrapper translates each tier into the actual
#: model id at call time, keeping the upgrade path (Gemini 3 Flash → 4
#: Flash) one constant away.
ModelTier = Literal["flash_2_5", "flash_3", "pro_3"]

#: Concrete model ids per tier. These can move with releases — the
#: orchestrator references the tier names, not the model ids, so a
#: model bump is a one-line change here.
_MODEL_BY_TIER: dict[ModelTier, str] = {
    "flash_2_5": "gemini-2.5-flash",
    "flash_3": "gemini-3-flash",
    "pro_3": "gemini-3-pro",
}

#: Bytes. Vertex's inline-data limit is 20 MB after base64; budgeting
#: 19 MB of raw input keeps us safely under once the SDK encodes.
MAX_INLINE_PDF_BYTES = 19 * 1024 * 1024

#: Default region by country bucket — UK audits land in europe-west2 to
#: keep payloads inside the EEA.
_DEFAULT_REGION_BY_COUNTRY: dict[str, Region] = {
    "US": "us-central1",
    "UK": "europe-west2",
    "GB": "europe-west2",
}


T = TypeVar("T", bound=BaseModel)


_log = get_logger(__name__)


class VertexConfigurationError(RuntimeError):
    """Raised at construction time when ZDR / region / project is unset."""


class VertexInputError(ValueError):
    """Raised when the caller hands the wrapper a payload it must reject."""


class VertexExtractionError(RuntimeError):
    """Raised when the upstream call or response parsing fails."""


def default_region_for_country(country: str) -> Region:
    """Region the wrapper will use when the caller doesn't pin one.

    Public so the orchestrator can derive a region from an audit's
    address country and pass it explicitly — keeps the routing logic
    out of the model layer.
    """
    return _DEFAULT_REGION_BY_COUNTRY.get(country.upper(), "us-central1")


def _build_default_client(*, location: Region) -> Any:
    """Construct the live ``google.genai.Client`` against Vertex.

    The only client-construction call site in the module — Vertex
    routing (vs the AI Studio surface at generativelanguage.googleapis.com)
    is enforced here at the source rather than via runtime introspection.
    """
    from google import genai  # noqa: PLC0415

    project = require(settings.vertex_project_id, "VERTEX_PROJECT_ID")
    return genai.Client(vertexai=True, project=project, location=location)


class VertexClient:
    """Typed Gemini extraction client pinned to a Vertex region + tier.

    A single instance can be reused across requests; ``extract`` accepts
    a per-call ``region`` override so the same client serves UK and US
    audits without re-instantiating. The default region falls back to
    ``settings.vertex_location``.
    """

    def __init__(
        self,
        *,
        region: Region | None = None,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        # ZDR is hard-required: a misconfigured deploy must not send
        # PDFs to a non-ZDR project.
        if not settings.vertex_zdr_enabled:
            raise VertexConfigurationError(
                "VERTEX_ZDR_ENABLED is false; ZDR is mandatory for proposal extraction "
                "(LEGAL_CONSIDERATIONS.md § G1b)."
            )
        if not settings.vertex_abuse_logging_exempt:
            raise VertexConfigurationError(
                "VERTEX_ABUSE_LOGGING_EXEMPT is false; ZDR requires the abuse-logging "
                "exception to be enrolled at the GCP project level."
            )

        self._region: Region = region or _coerce_region(settings.vertex_location)
        self._client_factory = client_factory or _build_default_client
        self._client = self._client_factory(location=self._region)

    @property
    def region(self) -> Region:
        return self._region

    async def extract(
        self,
        *,
        pdf_bytes: bytes,
        schema: type[T],
        model_tier: ModelTier = "flash_2_5",
        region: Region | None = None,
        system_prompt: str | None = None,
    ) -> T:
        """Run the model against ``pdf_bytes`` and parse into ``schema``.

        The PDF is sent inline (no Files API — see module docstring).
        ``schema`` must be a Pydantic ``BaseModel`` subclass; the SDK
        targets it via JSON-mode response constraint and we re-validate
        on this side so a malformed response surfaces as a clean
        :class:`VertexExtractionError` instead of leaking through.
        """
        if not pdf_bytes:
            raise VertexInputError("pdf_bytes is empty")
        if len(pdf_bytes) > MAX_INLINE_PDF_BYTES:
            raise VertexInputError(
                f"pdf_bytes is {len(pdf_bytes)} bytes; inline limit is "
                f"{MAX_INLINE_PDF_BYTES} bytes (chunk or downscale upstream)"
            )

        from google.genai import types  # noqa: PLC0415

        active_region: Region = region or self._region
        client = (
            self._client
            if active_region == self._region
            else self._client_factory(location=active_region)
        )

        part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
        config_kwargs: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": schema,
            # NB: ``cached_content`` is intentionally never set — context
            # caching is a ZDR violation. The escalation policy lives at
            # a higher layer (chart-solar-1yz) and re-issues calls; it
            # does not lean on prefix caching.
        }
        if system_prompt is not None:
            config_kwargs["system_instruction"] = system_prompt

        try:
            response = await client.aio.models.generate_content(
                model=_MODEL_BY_TIER[model_tier],
                contents=[part],
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:  # noqa: BLE001
            _log.error(
                "vertex.extract_failed",
                tier=model_tier,
                region=active_region,
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise VertexExtractionError(f"vertex extract failed: {exc!r}") from exc

        payload = response.text
        if not isinstance(payload, str) or not payload:
            raise VertexExtractionError("vertex response carried no text payload")
        try:
            return schema.model_validate_json(payload)
        except Exception as exc:  # noqa: BLE001
            raise VertexExtractionError(
                f"vertex returned a payload that does not match {schema.__name__}: {exc!r}"
            ) from exc


_ALLOWED_REGIONS: frozenset[Region] = frozenset(("us-central1", "us-east4", "europe-west2"))


def _coerce_region(value: str) -> Region:
    """Settings store the region as a free-form string; narrow it here."""
    if value not in _ALLOWED_REGIONS:
        raise VertexConfigurationError(
            f"vertex region {value!r} is not in the allow-list "
            f"({', '.join(sorted(_ALLOWED_REGIONS))})"
        )
    return value


__all__ = [
    "MAX_INLINE_PDF_BYTES",
    "ModelTier",
    "Region",
    "VertexClient",
    "VertexConfigurationError",
    "VertexExtractionError",
    "VertexInputError",
    "default_region_for_country",
]
