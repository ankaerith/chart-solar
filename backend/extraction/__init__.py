"""Vertex AI Gemini extraction — IO contracts.

This module is the *typed boundary* between the model (cognition) and
the rest of the app (deterministic). Per ZFC: schemas live here so the
model returns structured JSON; everything downstream is pure-Python and
testable with hand-written fixtures. No regex over installer names, no
template fingerprint dictionary in code — all of that is the model's
job, and its output is shaped by these schemas.
"""

from backend.extraction.critical_fields import (
    CRITICAL_FIELDS,
    critical_field_confidences,
    needs_user_review,
)
from backend.extraction.schemas import (
    BatteryEquipment,
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
)

__all__ = [
    "CRITICAL_FIELDS",
    "BatteryEquipment",
    "Extracted",
    "ExtractedProposal",
    "Financial",
    "Financing",
    "IncentiveClaim",
    "Installer",
    "InverterEquipment",
    "LineItem",
    "Operational",
    "PanelEquipment",
    "SystemEquipment",
    "critical_field_confidences",
    "needs_user_review",
]
