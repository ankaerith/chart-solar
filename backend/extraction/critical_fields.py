"""Critical-field registry + confidence helpers.

The four critical fields (gross price, kW-DC, panel count, year-1 kWh)
gate two policies: the audit pipeline refuses to ship if any of them
has confidence below `CRITICAL_FIELD_REVIEW_THRESHOLD`, and the
extraction step's escalation policy treats a low-confidence critical
field as a signal to retry against a stronger model tier.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from backend.extraction.schemas import Extracted, ExtractedProposal

CRITICAL_FIELDS: frozenset[str] = frozenset(
    {
        "financial.gross_system_price",
        "system.total_dc_kw",
        "system.panel_count",
        "financial.year_1_kwh_claim",
    }
)

# Below this confidence on a critical field, the audit pipeline must
# surface the field to the user for correction before producing the
# variance report. Tuned conservatively — false positives ("user, please
# confirm this") are cheap; false negatives ("we silently shipped a
# wrong audit") are not.
CRITICAL_FIELD_REVIEW_THRESHOLD: float = 0.75


def critical_field_confidences(proposal: ExtractedProposal) -> dict[str, float]:
    """Return `{dotted_path: confidence}` for every critical field."""
    out: dict[str, float] = {}
    for path in CRITICAL_FIELDS:
        extracted = _resolve(proposal, path)
        if isinstance(extracted, Extracted):
            out[path] = float(extracted.confidence)
    return out


def needs_user_review(
    proposal: ExtractedProposal,
    *,
    threshold: float = CRITICAL_FIELD_REVIEW_THRESHOLD,
) -> list[str]:
    """List of critical-field paths whose confidence falls below
    `threshold`. Empty list = audit can ship without user correction."""
    confidences = critical_field_confidences(proposal)
    return [path for path, conf in confidences.items() if conf < threshold]


def _resolve(model: Any, dotted_path: str) -> Any:
    parts = dotted_path.split(".")
    cur: Any = model
    for part in parts:
        if cur is None:
            return None
        cur = getattr(cur, part, None)
    return cur


def _validate_paths_against_schema() -> None:
    """Walk every CRITICAL_FIELDS path against ``ExtractedProposal``'s
    declared fields at import time so a schema rename / restructure
    fails the process boot rather than silently emptying
    ``critical_field_confidences()`` at audit time.
    """
    for path in CRITICAL_FIELDS:
        cls: type[BaseModel] = ExtractedProposal
        for part in path.split("."):
            field = cls.model_fields.get(part)
            if field is None:
                raise RuntimeError(
                    f"CRITICAL_FIELDS path {path!r} drifted from ExtractedProposal: "
                    f"no field named {part!r} on {cls.__name__}"
                )
            annotation = field.annotation
            origin = getattr(annotation, "__origin__", annotation)
            if isinstance(origin, type) and issubclass(origin, BaseModel):
                cls = origin
            else:
                # Reached a leaf (typically Extracted[T]); the next part of
                # the path, if any, is invalid.
                break


_validate_paths_against_schema()
