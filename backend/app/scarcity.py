"""
Compass — Scarcity signal engine.

Every scarcity string is strictly field-backed: a string is emitted ONLY when
its backing field is present and non-null. No field → no string. This is
auditable: TEMPLATE_REGISTRY maps each template to its field name, so tests
can enumerate the registry and assert the contract.

Templates:
  remaining_at_fare       → "{n} left at this fare"
  historically_sells_out_weeks → "tends to sell out ~{w} weeks out"
  holiday_overlap         → "overlaps {holiday}"
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Template registry
# Each entry: (field_name, format_fn)
# format_fn receives the field value and returns the display string.
# ---------------------------------------------------------------------------

TEMPLATE_REGISTRY: list[tuple[str, Any]] = [
    ("remaining_at_fare", lambda n: f"{n} left at this fare"),
    ("historically_sells_out_weeks", lambda w: f"tends to sell out ~{w} weeks out"),
    ("holiday_overlap", lambda h: f"overlaps {h}"),
]


def scarcity_for(obj: Any) -> list[str]:
    """
    Return a list of scarcity signal strings for a cruise or stateroom object.

    obj may be:
      - A Pydantic model (Cruise or StateroomCategory) with the relevant fields
      - A plain dict with string keys

    A string is emitted ONLY when the backing field is present and non-null.
    If no backing fields are present or all are None, returns [].

    Examples:
        scarcity_for(cruise_with_remaining_3) → ["3 left at this fare"]
        scarcity_for(cruise_with_no_fields)   → []
    """
    results = []

    for field_name, fmt_fn in TEMPLATE_REGISTRY:
        # Support both Pydantic models (attribute access) and dicts
        if isinstance(obj, dict):
            value = obj.get(field_name)
        else:
            value = getattr(obj, field_name, None)

        if value is not None:
            results.append(fmt_fn(value))

    return results
