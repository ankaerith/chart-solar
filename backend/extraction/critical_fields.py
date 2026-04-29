"""Critical-field registry + confidence helpers.

Per chart-solar-3hi: critical fields (gross price, kW-DC, panel count,
year-1 kWh) are flagged separately so the audit pipeline can:

* refuse to emit an audit if any critical field has confidence below
  the user-correction threshold (`needs_user_review`),
* feed the escalation policy — low confidence on a critical field is a
  signal to retry against a stronger model tier.

`CRITICAL_FIELDS` is a `frozenset` of dotted-path field names against
`ExtractedProposal`. Add a row here = one place to edit.
"""

from __future__ import annotations

from typing import Any

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
    """Return `{dotted_path: confidence}` for every critical field.

    Skips fields whose path doesn't resolve (defensive — schema drift
    surfaces as a missing key instead of a confidence value of 0)."""
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
