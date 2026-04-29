"""Pydantic tool-use schemas for proposal extraction.

The schemas ARE the IO contract between Gemini and the rest of the app
— so the tests cover the contract shape (every advertised field is
accepted, every invalid input is rejected, critical-field confidence
helpers work) rather than running Gemini itself. The model lives one
layer up; here we test the structure it has to fit into.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from backend.extraction import (
    CRITICAL_FIELDS,
    Extracted,
    ExtractedProposal,
    Financial,
    Financing,
    IncentiveClaim,
    Installer,
    InverterEquipment,
    LineItem,
    Operational,
    PanelEquipment,
    SystemEquipment,
    critical_field_confidences,
    needs_user_review,
)
from backend.extraction.critical_fields import CRITICAL_FIELD_REVIEW_THRESHOLD

# ---------------------------------------------------------------------------
# Extracted[T] generic
# ---------------------------------------------------------------------------


def test_extracted_accepts_value_with_confidence_and_quote() -> None:
    e: Extracted[float] = Extracted(value=8.0, confidence=0.95, source_quote="Total DC kW: 8.0")
    assert e.value == pytest.approx(8.0)
    assert e.confidence == pytest.approx(0.95)
    assert e.source_quote == "Total DC kW: 8.0"


def test_extracted_allows_value_none_so_model_can_say_not_stated() -> None:
    """The model should be allowed to return `value=None` when a field
    isn't stated on the proposal — beats hallucinating."""
    e: Extracted[float] = Extracted(value=None, confidence=1.0)
    assert e.value is None


def test_extracted_rejects_confidence_outside_unit_interval() -> None:
    with pytest.raises(ValidationError):
        Extracted[float](value=1.0, confidence=1.5)
    with pytest.raises(ValidationError):
        Extracted[float](value=1.0, confidence=-0.1)


# ---------------------------------------------------------------------------
# Equipment shapes
# ---------------------------------------------------------------------------


def test_panel_equipment_round_trips() -> None:
    panel = PanelEquipment(
        manufacturer=Extracted(value="Q CELLS", confidence=0.99),
        model=Extracted(value="Q.PEAK DUO BLK ML-G10+", confidence=0.95),
        rated_watts_stc=Extracted(value=410.0, confidence=0.99),
        warranty_years=Extracted(value=25, confidence=0.9),
    )
    assert panel.manufacturer.value == "Q CELLS"


def test_battery_equipment_optional_on_system() -> None:
    """A no-battery proposal must still validate."""
    sys = _full_system_equipment()
    assert sys.battery is None


def test_inverter_type_is_constrained() -> None:
    with pytest.raises(ValidationError):
        InverterEquipment(
            make=Extracted(value="x", confidence=0.5),
            model=Extracted(value="y", confidence=0.5),
            type=Extracted(value="not-a-valid-type", confidence=0.5),
            rated_kw=Extracted(value=7.6, confidence=0.5),
        )


# ---------------------------------------------------------------------------
# Financial shapes
# ---------------------------------------------------------------------------


def test_financing_validates_apr_in_zero_one() -> None:
    with pytest.raises(ValidationError):
        Financing(method="loan", term_years=20, apr=2.5)
    with pytest.raises(ValidationError):
        Financing(method="loan", term_years=0)


def test_incentive_claim_amount_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        IncentiveClaim(name="x", type="federal_itc", amount=-1.0)


def test_line_items_are_listed_and_kinds_constrained() -> None:
    fin = _full_financial()
    fin = fin.model_copy(
        update={
            "line_items": [
                LineItem(name="MPU upgrade", amount=2200.0, kind="adder"),
                LineItem(name="Sales tax", amount=425.0, kind="tax"),
            ]
        }
    )
    assert len(fin.line_items) == 2
    with pytest.raises(ValidationError):
        LineItem(name="x", amount=10.0, kind="not-a-kind")


# ---------------------------------------------------------------------------
# Top-level proposal
# ---------------------------------------------------------------------------


def test_full_proposal_round_trips_through_json() -> None:
    """Gemini returns JSON; ensure the entire shape parses + serialises
    without losing anything."""
    proposal = _full_proposal()
    serialised = proposal.model_dump(mode="json")
    revived = ExtractedProposal.model_validate(serialised)
    assert revived == proposal


def test_proposal_overall_confidence_in_unit_interval() -> None:
    with pytest.raises(ValidationError):
        ExtractedProposal(
            system=_full_system_equipment(),
            financial=_full_financial(),
            installer=_full_installer(),
            operational=_full_operational(),
            overall_confidence=1.2,
        )


def test_proposal_extraction_notes_optional() -> None:
    proposal = _full_proposal()
    assert proposal.extraction_notes is None


# ---------------------------------------------------------------------------
# Critical-field registry + helpers
# ---------------------------------------------------------------------------


def test_critical_fields_match_product_plan() -> None:
    """The four critical fields per PRODUCT_PLAN.md § Extraction field
    inventory: gross price, kW-DC, panel count, year-1 kWh."""
    assert CRITICAL_FIELDS == frozenset(
        {
            "financial.gross_system_price",
            "system.total_dc_kw",
            "system.panel_count",
            "financial.year_1_kwh_claim",
        }
    )


def test_critical_field_confidences_returns_one_entry_per_critical_field() -> None:
    proposal = _full_proposal()
    confidences = critical_field_confidences(proposal)
    assert set(confidences.keys()) == CRITICAL_FIELDS
    for value in confidences.values():
        assert 0.0 <= value <= 1.0


def test_needs_user_review_empty_when_all_critical_high_confidence() -> None:
    proposal = _full_proposal()
    assert needs_user_review(proposal) == []


def test_needs_user_review_lists_low_confidence_critical_fields() -> None:
    proposal = _full_proposal()
    # Tank confidence on one critical field — that field, and only that
    # field, should surface for user review.
    proposal.financial.gross_system_price = Extracted(
        value=29_500.0, confidence=0.40, source_quote="$29,500.00 (handwritten)"
    )
    flagged = needs_user_review(proposal)
    assert flagged == ["financial.gross_system_price"]


def test_needs_user_review_threshold_is_overrideable() -> None:
    """Audit can pass a stricter threshold (e.g., for high-stakes
    flows). Default is 0.75 — anything below is flagged."""
    proposal = _full_proposal()
    # Default threshold lets every fixture field (>= 0.90) through.
    assert needs_user_review(proposal, threshold=0.75) == []
    # year_1_kwh_claim is the lowest-confidence critical field in the
    # fixture (0.90). A threshold of 0.95 must flag it.
    flagged = needs_user_review(proposal, threshold=0.95)
    assert "financial.year_1_kwh_claim" in flagged


def test_critical_review_threshold_is_strict_enough_to_catch_uncertain_fields() -> None:
    """Sanity-check the chosen threshold (0.75): a 0.7 confidence
    extraction on a critical field MUST surface for review."""
    proposal = _full_proposal()
    proposal.system.total_dc_kw = Extracted(value=8.0, confidence=0.70)
    flagged = needs_user_review(proposal)
    assert "system.total_dc_kw" in flagged
    assert CRITICAL_FIELD_REVIEW_THRESHOLD == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# JSON-schema export sanity (this is what we send Gemini as the tool spec)
# ---------------------------------------------------------------------------


def test_extracted_proposal_emits_json_schema() -> None:
    """Gemini's structured-output tool config consumes JSON Schema; the
    model_json_schema() round-trip must succeed at module load — tests
    catch schema-drift early."""
    schema = ExtractedProposal.model_json_schema()
    assert "properties" in schema
    assert {"system", "financial", "installer", "operational"}.issubset(
        set(schema["properties"].keys())
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _full_system_equipment() -> SystemEquipment:
    return SystemEquipment(
        panel=PanelEquipment(
            manufacturer=Extracted(value="Q CELLS", confidence=0.99),
            model=Extracted(value="Q.PEAK DUO BLK ML-G10+ 410", confidence=0.95),
            rated_watts_stc=Extracted(value=410.0, confidence=0.99),
            warranty_years=Extracted(value=25, confidence=0.9),
        ),
        panel_count=Extracted(value=20, confidence=0.95),
        total_dc_kw=Extracted(value=8.2, confidence=0.99),
        total_ac_kw=Extracted(value=7.6, confidence=0.95),
        inverter=InverterEquipment(
            make=Extracted(value="Enphase", confidence=0.99),
            model=Extracted(value="IQ8M", confidence=0.95),
            type=Extracted(value="microinverter", confidence=0.99),
            rated_kw=Extracted(value=7.6, confidence=0.95),
        ),
        optimizers_present=Extracted(value=False, confidence=0.95),
        rapid_shutdown_present=Extracted(value=True, confidence=0.99),
        battery=None,
        mounting_type=Extracted(value="roof", confidence=0.99),
        tilt_deg=Extracted(value=22.0, confidence=0.85),
        azimuth_deg=Extracted(value=180.0, confidence=0.85),
        monitoring_platform=Extracted(value="Enphase Enlighten", confidence=0.95),
        monitoring_years_included=Extracted(value=10, confidence=0.85),
    )


def _full_financial() -> Financial:
    return Financial(
        gross_system_price=Extracted(value=29_500.0, confidence=0.99),
        dollar_per_watt=Extracted(value=3.60, confidence=0.95),
        line_items=[],
        incentives_claimed=[
            IncentiveClaim(name="Federal ITC", type="federal_itc", amount=8_850.0),
        ],
        net_price_after_incentives=Extracted(value=20_650.0, confidence=0.99),
        financing=Extracted(
            value=Financing(method="cash"),
            confidence=0.99,
        ),
        assumed_escalator=Extracted(value=0.025, confidence=0.85),
        assumed_degradation=Extracted(value=0.005, confidence=0.85),
        year_1_kwh_claim=Extracted(value=10_400.0, confidence=0.90),
        twenty_year_savings_claim=Extracted(value=58_000.0, confidence=0.85),
        payback_year_claimed=Extracted(value=8.5, confidence=0.85),
    )


def _full_installer() -> Installer:
    return Installer(
        company_name=Extracted(value="Sunny Solar Co", confidence=0.99),
        license_number=Extracted(value="WA-SOLAR-12345", confidence=0.95),
        address=Extracted(value="123 Roof Lane, Seattle WA 98101", confidence=0.95),
        phone=Extracted(value="555-0100", confidence=0.95),
        rep_name=Extracted(value="Pat Example", confidence=0.95),
        quote_date=Extracted(value=date(2026, 4, 15), confidence=0.99),
        expiration_date=Extracted(value=date(2026, 5, 15), confidence=0.95),
        nabcep_certified=Extracted(value=True, confidence=0.85),
        installation_timeline_weeks=Extracted(value=8, confidence=0.85),
        workmanship_warranty_years=Extracted(value=10, confidence=0.85),
    )


def _full_operational() -> Operational:
    return Operational(
        shading_assumption=Extracted(value="< 5%", confidence=0.85),
        production_estimate_source=Extracted(value="pvwatts", confidence=0.95),
        monitoring_years_free=Extracted(value=10, confidence=0.85),
        service_agreement_terms=Extracted(value=None, confidence=0.95),
    )


def _full_proposal() -> ExtractedProposal:
    return ExtractedProposal(
        system=_full_system_equipment(),
        financial=_full_financial(),
        installer=_full_installer(),
        operational=_full_operational(),
        overall_confidence=0.92,
        needs_stronger_model=False,
    )


# Quiet the linter — `Any` is referenced via casts in some helpers.
_ = Any
