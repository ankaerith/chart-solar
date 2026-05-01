"""Extraction orchestrator tests — heuristics + tier router + review flag.

Covers chart-solar-78j AC1-5:
1. PDF bytes → heuristics → tier → vertex.extract → typed result
2. Heuristics detect file size, page count, image-only, password-protected, multi-bid
3. needs_user_review flips when any critical field's confidence < threshold
4. Structured trace per extraction (no PDF body, no PII)
5. Digital sample → flash_2_5; scanned sample → flash_3 escalation

The Vertex client is stubbed via the ``VertexExtractor`` Protocol;
heuristics are constructed directly via ``PdfHeuristics`` so the
orchestrator's tier-router and confidence logic are exercised
without depending on PDF-byte construction (covered separately in
``test_extraction_heuristics.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pytest

from backend.extraction.heuristics import PdfHeuristics
from backend.extraction.schemas import (
    Extracted,
    ExtractedProposal,
    Financial,
    Financing,
    Installer,
    InverterEquipment,
    Operational,
    PanelEquipment,
    SystemEquipment,
)
from backend.services.extraction import (
    CRITICAL_CONFIDENCE_THRESHOLD,
    ExtractionRefused,
    critical_field_confidences,
    extract_proposal,
    needs_user_review,
    pick_model_tier,
)

# ---------------------------------------------------------------------------
# Stub PdfHeuristics + ExtractedProposal builders
# ---------------------------------------------------------------------------


def _heuristics(
    *,
    file_size_bytes: int = 1_000_000,
    page_count: int = 8,
    is_image_only: bool = False,
    top_level_bookmarks: int = 0,
    text_density: float = 800.0,
    is_password_protected: bool = False,
) -> PdfHeuristics:
    return PdfHeuristics(
        file_size_bytes=file_size_bytes,
        page_count=page_count,
        is_password_protected=is_password_protected,
        is_image_only=is_image_only,
        text_density=text_density,
        top_level_bookmarks=top_level_bookmarks,
    )


def _proposal(
    *,
    panel_count_conf: float = 0.95,
    total_dc_kw_conf: float = 0.95,
    gross_price_conf: float = 0.95,
    year_one_kwh_conf: float = 0.95,
    overall: float = 0.95,
) -> ExtractedProposal:
    return ExtractedProposal(
        system=SystemEquipment(
            panel=PanelEquipment(
                manufacturer=Extracted(value="Q Cells", confidence=0.99),
                model=Extracted(value="Q.Peak", confidence=0.99),
                rated_watts_stc=Extracted(value=400.0, confidence=0.99),
                warranty_years=Extracted(value=25, confidence=0.99),
            ),
            panel_count=Extracted(value=24, confidence=panel_count_conf),
            total_dc_kw=Extracted(value=9.6, confidence=total_dc_kw_conf),
            total_ac_kw=Extracted(value=8.5, confidence=0.95),
            inverter=InverterEquipment(
                make=Extracted(value="Enphase", confidence=0.95),
                model=Extracted(value="IQ8+", confidence=0.95),
                type=Extracted(value="microinverter", confidence=0.95),
                rated_kw=Extracted(value=8.5, confidence=0.95),
            ),
            optimizers_present=Extracted(value=False, confidence=0.95),
            rapid_shutdown_present=Extracted(value=True, confidence=0.95),
            mounting_type=Extracted(value="roof", confidence=0.95),
        ),
        financial=Financial(
            gross_system_price=Extracted(value=29_000.0, confidence=gross_price_conf),
            dollar_per_watt=Extracted(value=3.0, confidence=0.95),
            net_price_after_incentives=Extracted(value=22_000.0, confidence=0.95),
            financing=Extracted(
                value=Financing(method="cash"),
                confidence=0.95,
            ),
            year_1_kwh_claim=Extracted(value=12_500.0, confidence=year_one_kwh_conf),
        ),
        installer=Installer(
            company_name=Extracted(value="Sunco", confidence=0.95),
            quote_date=Extracted(value="2026-04-01", confidence=0.95),
        ),
        operational=Operational(
            production_estimate_source=Extracted(value="pvwatts", confidence=0.95),
        ),
        overall_confidence=overall,
    )


# ---------------------------------------------------------------------------
# Tier router (pure)
# ---------------------------------------------------------------------------


def test_tier_router_defaults_to_flash_2_5_for_small_digital() -> None:
    assert pick_model_tier(_heuristics()) == "flash_2_5"


def test_tier_router_escalates_image_only_to_flash_3() -> None:
    assert pick_model_tier(_heuristics(is_image_only=True)) == "flash_3"


def test_tier_router_escalates_large_files_to_flash_3() -> None:
    big = _heuristics(file_size_bytes=10 * 1024 * 1024)
    assert pick_model_tier(big) == "flash_3"


def test_tier_router_escalates_long_docs_to_flash_3() -> None:
    long_doc = _heuristics(page_count=40)
    assert pick_model_tier(long_doc) == "flash_3"


def test_tier_router_escalates_multibid_to_pro_3() -> None:
    multi = _heuristics(top_level_bookmarks=4)
    assert pick_model_tier(multi) == "pro_3"


def test_tier_router_multibid_beats_image_only() -> None:
    """Multi-bid signal dominates other escalation triggers."""
    both = _heuristics(top_level_bookmarks=4, is_image_only=True)
    assert pick_model_tier(both) == "pro_3"


# ---------------------------------------------------------------------------
# Critical-field confidence + review flag
# ---------------------------------------------------------------------------


def test_critical_field_confidences_picks_the_four_fields() -> None:
    confs = critical_field_confidences(_proposal())
    assert set(confs.keys()) == {
        "gross_system_price",
        "total_dc_kw",
        "panel_count",
        "year_1_kwh_claim",
    }
    assert all(v == 0.95 for v in confs.values())


def test_needs_user_review_false_when_all_critical_above_threshold() -> None:
    assert needs_user_review(_proposal()) is False


def test_needs_user_review_true_when_any_critical_below_threshold() -> None:
    p = _proposal(panel_count_conf=CRITICAL_CONFIDENCE_THRESHOLD - 0.01)
    assert needs_user_review(p) is True


# ---------------------------------------------------------------------------
# Stub Vertex
# ---------------------------------------------------------------------------


@dataclass
class _RecordedExtract:
    pdf_bytes: bytes
    schema: type
    model_tier: str
    region: str
    system_prompt: str | None


@dataclass
class _StubVertex:
    region: Literal["us-central1", "us-east4", "europe-west2"] = "us-central1"
    response: ExtractedProposal = field(default_factory=_proposal)
    calls: list[_RecordedExtract] = field(default_factory=list)
    raise_input_error: str | None = None

    async def extract(
        self,
        *,
        pdf_bytes: bytes,
        schema: type,
        model_tier: Literal["flash_2_5", "flash_3", "pro_3"],
        region: Literal["us-central1", "us-east4", "europe-west2"],
        system_prompt: str | None = None,
    ) -> ExtractedProposal:
        self.calls.append(
            _RecordedExtract(
                pdf_bytes=pdf_bytes,
                schema=schema,
                model_tier=model_tier,
                region=region,
                system_prompt=system_prompt,
            )
        )
        if self.raise_input_error is not None:
            from backend.services.vertex_client import VertexInputError

            raise VertexInputError(self.raise_input_error)
        return self.response


# ---------------------------------------------------------------------------
# Orchestrator end-to-end with injected heuristics + stub Vertex
# ---------------------------------------------------------------------------


async def test_extract_proposal_routes_digital_sample_to_flash_2_5() -> None:
    vertex = _StubVertex()
    result = await extract_proposal(
        b"%PDF",
        vertex=vertex,
        heuristics=_heuristics(),  # default = small digital
    )
    assert vertex.calls[0].model_tier == "flash_2_5"
    assert result.needs_user_review is False
    assert result.trace.is_image_only is False


async def test_extract_proposal_escalates_scanned_sample_to_flash_3() -> None:
    vertex = _StubVertex()
    await extract_proposal(
        b"%PDF",
        vertex=vertex,
        heuristics=_heuristics(is_image_only=True, text_density=0.0),
    )
    assert vertex.calls[0].model_tier == "flash_3"


async def test_extract_proposal_escalates_multibid_to_pro_3() -> None:
    vertex = _StubVertex()
    await extract_proposal(
        b"%PDF",
        vertex=vertex,
        heuristics=_heuristics(top_level_bookmarks=4),
    )
    assert vertex.calls[0].model_tier == "pro_3"


async def test_extract_proposal_flips_review_flag_on_low_confidence() -> None:
    vertex = _StubVertex(response=_proposal(panel_count_conf=0.4))
    result = await extract_proposal(
        b"%PDF",
        vertex=vertex,
        heuristics=_heuristics(),
    )
    assert result.needs_user_review is True
    assert result.trace.critical_field_confidences["panel_count"] == 0.4


async def test_extract_proposal_passes_region_through_to_vertex() -> None:
    vertex = _StubVertex(region="us-central1")
    await extract_proposal(
        b"%PDF",
        vertex=vertex,
        region="europe-west2",
        heuristics=_heuristics(),
    )
    assert vertex.calls[0].region == "europe-west2"


async def test_extract_proposal_refuses_password_protected_without_calling_vertex() -> None:
    vertex = _StubVertex()
    with pytest.raises(ExtractionRefused, match="password-protected"):
        await extract_proposal(
            b"%PDF",
            vertex=vertex,
            heuristics=_heuristics(is_password_protected=True),
        )
    assert vertex.calls == []


async def test_extract_proposal_refuses_unreadable_pdf_without_calling_vertex() -> None:
    vertex = _StubVertex()
    with pytest.raises(ExtractionRefused, match="no pages or is unreadable"):
        await extract_proposal(
            b"not-a-pdf",
            vertex=vertex,
            heuristics=_heuristics(page_count=0),
        )
    assert vertex.calls == []


async def test_extract_proposal_refuses_oversize_via_vertex_input_error() -> None:
    vertex = _StubVertex(raise_input_error="pdf_bytes is 25000000 bytes; inline limit is …")
    with pytest.raises(ExtractionRefused, match="inline limit"):
        await extract_proposal(
            b"%PDF",
            vertex=vertex,
            heuristics=_heuristics(),
        )


async def test_extract_proposal_trace_carries_no_pdf_body_or_pii(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The structured trace logged by the orchestrator must not include
    PDF bytes or any installer / equipment string from the response."""
    import logging

    caplog.set_level(logging.INFO)
    vertex = _StubVertex()
    await extract_proposal(
        b"%PDF-1.4 ... fake bytes here",
        vertex=vertex,
        heuristics=_heuristics(),
    )
    log_text = caplog.text
    assert "%PDF" not in log_text
    assert "Sunco" not in log_text
    assert "Q Cells" not in log_text
    assert "fake bytes here" not in log_text


async def test_extract_proposal_default_heuristics_path_falls_back_to_inspect_pdf() -> None:
    """Without an injected ``heuristics``, the orchestrator calls
    ``inspect_pdf`` itself — exercise that seam against bytes that
    pypdf treats as unreadable so we land in ExtractionRefused."""
    vertex = _StubVertex()
    with pytest.raises(ExtractionRefused, match="no pages or is unreadable"):
        await extract_proposal(b"definitely not a pdf", vertex=vertex)
