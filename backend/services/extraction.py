"""Extraction orchestrator: PDF bytes → typed proposal + needs-review flag.

Composes :mod:`backend.extraction.heuristics` (cheap structural facts)
with :mod:`backend.services.vertex_client` (the model call) and the
:class:`backend.extraction.schemas.ExtractedProposal` schema. The result
is the structured proposal plus a ``needs_user_review`` boolean the
audit UI honors to decide which fields to surface for HITL correction.

Design choices:

* **Tier routing is a deterministic floor** (Pattern A in chart-solar-1yz).
  The model's self-reported ``needs_stronger_model`` flag is *not*
  consulted here — that's the hybrid escalation in the next ticket.
  Today we pick once, up-front, off the heuristics.
* **Critical-field threshold is the only confidence escape hatch**.
  Any of ``gross_system_price``, ``total_dc_kw``, ``panel_count``,
  ``year_1_kwh_claim`` below ``CRITICAL_CONFIDENCE_THRESHOLD`` flips
  ``needs_user_review`` so the HITL screen knows to ask.
* **No PDF bytes in logs**. Per the bead's AC4: structured trace per
  extraction with file size + page count + tier + confidences only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.extraction.heuristics import PdfHeuristics, inspect_pdf
from backend.extraction.schemas import ExtractedProposal
from backend.infra.logging import get_logger
from backend.services.vertex_client import (
    ModelTier,
    Region,
    VertexInputError,
)


class VertexExtractor(Protocol):
    """Structural protocol for the Vertex client.

    Pinned here (rather than imported from ``vertex_client``) so the
    orchestrator's tests can hand in any object that exposes the same
    surface — the live :class:`backend.services.vertex_client.VertexClient`
    satisfies it; in-test stubs do too without inheriting.
    """

    region: Region

    async def extract(
        self,
        *,
        pdf_bytes: bytes,
        schema: type[ExtractedProposal],
        model_tier: ModelTier,
        region: Region,
        system_prompt: str | None = None,
    ) -> ExtractedProposal: ...


_log = get_logger(__name__)

#: Below this self-reported confidence on a critical field, the result
#: is flagged ``needs_user_review`` so the HITL screen surfaces the
#: field for inline edit.
CRITICAL_CONFIDENCE_THRESHOLD = 0.7

#: Bytes — files larger than this take long enough to round-trip on
#: Flash 2.5 that we just go to the stronger-vision tier directly.
_LARGE_FILE_BYTES = 5 * 1024 * 1024

#: Page count above which we escalate. Single-bid proposals are
#: typically 6-15 pages; over 20 means either deep proprietary
#: appendices or a multi-bid layout.
_LARGE_PAGE_COUNT = 20

#: A PDF whose outline lists this many top-level bookmarks is usually
#: a multi-bid stapler (one bookmark per installer's section); we send
#: it to the strongest model.
_MULTI_BID_BOOKMARK_THRESHOLD = 3


class ExtractionRefused(RuntimeError):  # noqa: N818
    """Raised when the file fails the upstream guard (encrypted, too large).

    Named ``Refused`` (not ``RefusedError``) because callers raise it as
    a control-flow signal, not an unexpected error — the orchestrator
    deliberately rejects the file and the API translates that into
    422 with a helpful message.
    """


@dataclass(frozen=True)
class ExtractionTrace:
    """Structured per-extraction trace — ends up in the audit log row.

    Excludes the PDF bytes + every PII field; carries only structural
    facts + the tier picked + the per-critical-field confidences.
    """

    file_size_bytes: int
    page_count: int
    is_image_only: bool
    text_density: float
    top_level_bookmarks: int
    model_tier: ModelTier
    region: Region
    overall_confidence: float
    critical_field_confidences: dict[str, float]


@dataclass(frozen=True)
class ExtractionResult:
    """The orchestrator's payload — proposal + review flag + trace."""

    proposal: ExtractedProposal
    needs_user_review: bool
    trace: ExtractionTrace


def pick_model_tier(heuristics: PdfHeuristics) -> ModelTier:
    """Map structural facts onto a model tier.

    Multi-bid signals dominate (Pro for the multi-section narrative);
    image-only or large/long docs go to Flash 3 for stronger vision +
    longer context; everything else lands on Flash 2.5.
    """
    if heuristics.top_level_bookmarks >= _MULTI_BID_BOOKMARK_THRESHOLD:
        return "pro_3"
    if (
        heuristics.is_image_only
        or heuristics.file_size_bytes >= _LARGE_FILE_BYTES
        or heuristics.page_count >= _LARGE_PAGE_COUNT
    ):
        return "flash_3"
    return "flash_2_5"


def critical_field_confidences(proposal: ExtractedProposal) -> dict[str, float]:
    """Pluck the four critical fields' self-reported confidences."""
    return {
        "gross_system_price": proposal.financial.gross_system_price.confidence,
        "total_dc_kw": proposal.system.total_dc_kw.confidence,
        "panel_count": proposal.system.panel_count.confidence,
        "year_1_kwh_claim": proposal.financial.year_1_kwh_claim.confidence,
    }


def needs_user_review(proposal: ExtractedProposal) -> bool:
    """True if any critical field is below the confidence threshold.

    Sub-threshold confidence on a non-critical field does *not* trip
    review — the HITL screen would drown the user. Only the four
    fields the audit math depends on count.
    """
    return any(
        conf < CRITICAL_CONFIDENCE_THRESHOLD
        for conf in critical_field_confidences(proposal).values()
    )


async def extract_proposal(
    pdf_bytes: bytes,
    *,
    vertex: VertexExtractor,
    region: Region | None = None,
    system_prompt: str | None = None,
    heuristics: PdfHeuristics | None = None,
) -> ExtractionResult:
    """One-shot extraction: heuristics → tier route → Vertex → trace.

    ``vertex`` is injected so tests can supply a stub; production
    callers construct one off ``settings.vertex_*`` (see
    :class:`backend.services.vertex_client.VertexClient`). ``region``
    overrides the per-call routing if the audit knows its country
    upstream (see :func:`vertex_client.default_region_for_country`).

    ``heuristics`` overrides the default :func:`inspect_pdf` call —
    callers that already have a structural snapshot (e.g. the upload
    pipeline computed it for size-policy enforcement) can pass it in
    to avoid re-inspecting; tests use this seam to exercise the tier
    router with hand-crafted snapshots.

    Raises :class:`ExtractionRefused` when the file fails the
    structural guard (password-protected, exceeds Vertex's inline
    ceiling). The Vertex client itself raises
    :class:`backend.services.vertex_client.VertexExtractionError`
    on upstream failure; we don't wrap that — the caller already
    expects it.
    """
    snapshot = heuristics or inspect_pdf(pdf_bytes)

    if snapshot.is_password_protected:
        raise ExtractionRefused(
            "PDF is password-protected; ask the customer to re-export without a password"
        )
    if snapshot.page_count == 0:
        raise ExtractionRefused("PDF carries no pages or is unreadable")

    tier = pick_model_tier(snapshot)
    active_region = region or vertex.region

    try:
        proposal = await vertex.extract(
            pdf_bytes=pdf_bytes,
            schema=ExtractedProposal,
            model_tier=tier,
            region=active_region,
            system_prompt=system_prompt,
        )
    except VertexInputError as exc:
        # The 19MB cap lives in the Vertex client; surface it as an
        # ExtractionRefused so the caller treats it as a structural
        # rejection rather than an upstream model failure.
        raise ExtractionRefused(str(exc)) from exc

    review = needs_user_review(proposal)
    confidences = critical_field_confidences(proposal)

    trace = ExtractionTrace(
        file_size_bytes=snapshot.file_size_bytes,
        page_count=snapshot.page_count,
        is_image_only=snapshot.is_image_only,
        text_density=snapshot.text_density,
        top_level_bookmarks=snapshot.top_level_bookmarks,
        model_tier=tier,
        region=active_region,
        overall_confidence=proposal.overall_confidence,
        critical_field_confidences=confidences,
    )

    _log.info(
        "extraction.complete",
        # Per AC4: no PDF body, no PII; only structural facts + scores.
        file_size_bytes=trace.file_size_bytes,
        page_count=trace.page_count,
        is_image_only=trace.is_image_only,
        top_level_bookmarks=trace.top_level_bookmarks,
        model_tier=trace.model_tier,
        region=trace.region,
        overall_confidence=trace.overall_confidence,
        needs_user_review=review,
        **{f"conf_{k}": v for k, v in confidences.items()},
    )

    return ExtractionResult(
        proposal=proposal,
        needs_user_review=review,
        trace=trace,
    )


__all__ = [
    "CRITICAL_CONFIDENCE_THRESHOLD",
    "ExtractionRefused",
    "ExtractionResult",
    "ExtractionTrace",
    "critical_field_confidences",
    "extract_proposal",
    "needs_user_review",
    "pick_model_tier",
]
