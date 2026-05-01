"""Pre-Vertex heuristics: cheap PDF inspection that drives tier routing.

Pure deterministic checks against the raw bytes — file size, page
count, password-protection, scanned-vs-digital text density, and
multi-bid signals (bookmark fan-out). The orchestrator
(:mod:`backend.services.extraction`) consumes
:class:`PdfHeuristics` to decide which model tier to call and whether
the doc is even processable in the first place.

Why heuristics here, not in the model: model time is the expensive
resource. A 25 MB scanned multi-bid wants Gemini Pro; a 200 KB digital
single-bid is fine on Flash 2.5. The only way to make that decision
without burning a probe call is structured upstream inspection. Per
ZFC discipline (PRODUCT_PLAN.md § Cognition Architecture), this
module produces structured *facts* about the file, not classifications
about the *content*: "5 bookmarks at depth 1" is a fact; "this is a
multi-bid quote" is the model's call to make from those facts +
the rendered pages.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from pypdf import PdfReader
from pypdf.errors import PdfReadError


@dataclass(frozen=True)
class PdfHeuristics:
    """Structural snapshot of a PDF used by the tier router.

    ``is_password_protected`` short-circuits the orchestrator (we
    refuse the upload before spending model tokens). ``text_density``
    is the average extracted-text length per page; near-zero means
    the doc is image-only / scanned and the orchestrator escalates to
    a stronger model whose vision is better. ``top_level_bookmarks``
    is the count of bookmarks at the outline root — a proxy for
    multi-bid layouts where each installer's section gets its own
    bookmark.
    """

    file_size_bytes: int
    page_count: int
    is_password_protected: bool
    is_image_only: bool
    text_density: float
    top_level_bookmarks: int


# Below this average characters-per-page we treat the document as
# image-only / scanned. Empirically, even a sparse digital proposal
# clears 100 chars/page (header, page number, a few labels); scanned
# pages without an OCR layer return 0–20 from pypdf.
_IMAGE_ONLY_TEXT_DENSITY = 50.0


def inspect_pdf(pdf_bytes: bytes) -> PdfHeuristics:
    """Inspect ``pdf_bytes`` and return its structural snapshot.

    Tolerates partially-valid PDFs: if pypdf can open it but a single
    page extraction fails, that page contributes 0 characters to the
    density and the rest still reports. A password-protected PDF
    returns a ``PdfHeuristics`` with ``is_password_protected=True``
    and zeros elsewhere — the orchestrator refuses it without further
    work.
    """
    file_size = len(pdf_bytes)
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except PdfReadError:
        # Truly unreadable. Treat as image-only / unknown so the
        # orchestrator can escalate or reject upstream.
        return PdfHeuristics(
            file_size_bytes=file_size,
            page_count=0,
            is_password_protected=False,
            is_image_only=True,
            text_density=0.0,
            top_level_bookmarks=0,
        )

    if reader.is_encrypted:
        return PdfHeuristics(
            file_size_bytes=file_size,
            page_count=0,
            is_password_protected=True,
            is_image_only=False,
            text_density=0.0,
            top_level_bookmarks=0,
        )

    page_count = len(reader.pages)
    chars_total = 0
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 — single-page failures are tolerated
            text = ""
        chars_total += len(text)

    text_density = chars_total / page_count if page_count else 0.0
    is_image_only = page_count > 0 and text_density < _IMAGE_ONLY_TEXT_DENSITY
    top_level = _count_top_level_bookmarks(reader)

    return PdfHeuristics(
        file_size_bytes=file_size,
        page_count=page_count,
        is_password_protected=False,
        is_image_only=is_image_only,
        text_density=text_density,
        top_level_bookmarks=top_level,
    )


def _count_top_level_bookmarks(reader: PdfReader) -> int:
    """Count entries at the root of the outline; nested children don't count.

    Multi-bid PDFs typically bookmark each installer's section at the
    root level; a single-bid PDF either has no outline or a single
    "Cover Page" entry at the root.
    """
    try:
        outlines = reader.outline
    except Exception:  # noqa: BLE001 — pypdf can raise on malformed outlines
        return 0
    return sum(1 for entry in outlines if not isinstance(entry, list))


__all__ = ["PdfHeuristics", "inspect_pdf"]
