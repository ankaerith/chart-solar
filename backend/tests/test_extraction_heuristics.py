"""Heuristics tests using ``pypdf`` writer to construct valid PDFs.

Hand-rolling PDF byte literals is fragile (xref offsets / content
streams are easy to get wrong). pypdf's ``PdfWriter`` builds valid
PDFs we can introspect through the same library — that's the cleanest
way to assert heuristics behaviour against real bytes.

The orchestrator-side tier-router tests live in
``test_services_extraction.py`` and inject ``PdfHeuristics`` directly
without going through PDF construction.
"""

from __future__ import annotations

import io

from pypdf import PdfWriter

from backend.extraction.heuristics import inspect_pdf


def _blank_page_pdf(*, pages: int = 1, outline_titles: list[str] | None = None) -> bytes:
    """Build a multi-page PDF with optional top-level outline entries."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if outline_titles:
        for i, title in enumerate(outline_titles):
            writer.add_outline_item(title, i)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_inspect_blank_pdf_is_image_only() -> None:
    h = inspect_pdf(_blank_page_pdf())
    assert h.page_count == 1
    assert h.is_image_only is True
    assert h.text_density < 50.0
    assert h.is_password_protected is False


def test_inspect_multipage_blank_counts_pages() -> None:
    h = inspect_pdf(_blank_page_pdf(pages=4))
    assert h.page_count == 4


def test_inspect_unreadable_bytes_returns_zeroed_image_only() -> None:
    h = inspect_pdf(b"definitely not a pdf")
    assert h.page_count == 0
    assert h.is_image_only is True
    assert h.is_password_protected is False


def test_inspect_top_level_bookmarks_signal_multibid() -> None:
    h = inspect_pdf(
        _blank_page_pdf(
            pages=4,
            outline_titles=["Sunco bid", "Brightline bid", "Solar Co bid", "Sunpower bid"],
        )
    )
    assert h.top_level_bookmarks == 4


def test_inspect_no_outline_returns_zero_top_level() -> None:
    h = inspect_pdf(_blank_page_pdf())
    assert h.top_level_bookmarks == 0


def test_inspect_records_file_size() -> None:
    pdf_bytes = _blank_page_pdf()
    h = inspect_pdf(pdf_bytes)
    assert h.file_size_bytes == len(pdf_bytes)
