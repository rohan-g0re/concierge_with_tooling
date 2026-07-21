"""
Compass — draft management tools: create_draft, set_fare, set_stateroom.

Booking-step rules (PRD §7.1 / R23):
  completed_steps ⊆ {1, 2, 3, 4, 5}
  checkout_entry = min({1,2,3,4,5} - completed_steps)
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..models import Session, Draft

from ..catalog.loader import get_catalog
from ..money import draft_total, format_money

_DRAFT_CAP = 5
_ALL_STEPS = {1, 2, 3, 4, 5}

ANCHOR_DATE = "2026-07-01"


def _pick_sailing(cruise, constraints):
    """
    Pick the best sailing for a cruise given session constraints.

    Selection rules (mirrors search_cruises date logic):
      - If constraints.month set: earliest sailing whose departure_date month matches.
      - If constraints.return_by set: latest sailing whose return_date <= return_by.
      - If both set: both constraints applied, then earliest.
      - Else: next upcoming sailing with departure_date >= ANCHOR_DATE.
      - Fall back to first sailing if no constraint-satisfying sailing found.

    Returns a Sailing object, or None if cruise has no sailings.
    """
    sailings = getattr(cruise, "sailings", []) or []
    if not sailings:
        return None

    candidates = list(sailings)

    if constraints and constraints.month:
        month_matches = [s for s in candidates if int(s.departure_date.split("-")[1]) == constraints.month]
        if month_matches:
            candidates = month_matches
        # else fall through with all sailings

    if constraints and constraints.return_by:
        by_matches = [s for s in candidates if s.return_date <= constraints.return_by]
        if by_matches:
            candidates = by_matches
        # else fall through

    if constraints and constraints.month:
        # earliest matching
        return min(candidates, key=lambda s: s.departure_date)

    if constraints and constraints.return_by:
        # latest returning on/before — already filtered above
        return min(candidates, key=lambda s: s.departure_date)

    # Next upcoming >= anchor
    upcoming = [s for s in candidates if s.departure_date >= ANCHOR_DATE]
    if upcoming:
        return min(upcoming, key=lambda s: s.departure_date)

    # fallback: first sailing
    return sailings[0]


def checkout_entry(draft: "Draft") -> int:
    """Return the next booking step: min of steps not yet completed."""
    completed = set(draft.completed_steps)
    remaining = _ALL_STEPS - completed
    if not remaining:
        return 6  # all steps done
    return min(remaining)


def _recompute_totals(draft: "Draft", catalog: dict, party: int) -> None:
    """Recompute and update total_per_person and total on draft in place."""
    total = draft_total(draft, catalog, party=party)
    # total_per_person: divide by party (avoid div by 0)
    draft.total = total
    draft.total_per_person = total // party if party > 0 else total


def create_draft(session: "Session", args: dict) -> dict:
    """
    Create a new draft for a cruise and add it to session.

    Args:
        session: current session
        args: {"cruise_id": str}

    Returns:
        dict with draft info, or {"error": "draft_cap", "message": ...} if at cap
    """
    from ..models import Draft, DraftStateroom

    # Enforce cap
    if len(session.drafts) >= _DRAFT_CAP:
        return {
            "error": "draft_cap",
            "message": "You already have five drafts — delete one before starting another.",
        }

    cruise_id = args.get("cruise_id")
    if not cruise_id:
        return {"error": "missing_cruise_id", "message": "cruise_id is required"}

    catalog = get_catalog()
    cruise = next(
        (c for c in catalog["cruises"] if c.cruise_id == cruise_id), None
    )
    if cruise is None:
        return {"error": "cruise_not_found", "message": f"Cruise {cruise_id!r} not found"}

    # Resolve sailing
    sailing_id_arg = args.get("sailing_id")
    if sailing_id_arg:
        sailing = next(
            (s for s in (cruise.sailings or []) if s.sailing_id == sailing_id_arg), None
        )
        if sailing is None:
            return {
                "error": "sailing_not_found",
                "message": f"Sailing {sailing_id_arg!r} not found for cruise {cruise_id!r}",
            }
    else:
        sailing = _pick_sailing(cruise, session.constraints)

    draft_id = str(uuid.uuid4())
    draft = Draft(
        draft_id=draft_id,
        cruise_id=cruise_id,
        label=cruise.name,
        fare_package="good_to_go",
        stateroom=DraftStateroom(category="Inside", location=None),
        completed_steps=[1],
    )

    # Set sailing dates
    if sailing is not None:
        draft.sailing_id = sailing.sailing_id
        draft.departure_date = sailing.departure_date
        draft.return_date = sailing.return_date

    # Compute initial total
    _recompute_totals(draft, catalog, party=session.party)

    session.drafts.append(draft)
    session.active_draft_id = draft_id

    return {
        "draft_id": draft_id,
        "cruise_id": cruise_id,
        "label": draft.label,
        "completed_steps": list(draft.completed_steps),
        "checkout_entry": checkout_entry(draft),
        "total": draft.total,
        "total_formatted": format_money(draft.total) if draft.total is not None else None,
        "sailing_id": draft.sailing_id,
        "departure_date": draft.departure_date,
        "return_date": draft.return_date,
    }


def set_fare(session: "Session", args: dict) -> dict:
    """
    Set the fare package on a draft and recompute totals.

    Args:
        session: current session
        args: {"draft_id": str, "package": "good_to_go"|"have_it_all"}

    Returns:
        dict with updated draft info
    """
    draft_id = args.get("draft_id")
    package = args.get("package")

    draft = _find_draft(session, draft_id)
    if draft is None:
        return {"error": "draft_not_found", "message": f"Draft {draft_id!r} not found"}

    # Validate package
    if package not in ("good_to_go", "have_it_all"):
        return {"error": "invalid_package", "message": f"Package must be good_to_go or have_it_all, got {package!r}"}

    old_total = draft.total or 0
    draft.fare_package = package  # type: ignore[assignment]

    # Mark step 2
    if 2 not in draft.completed_steps:
        draft.completed_steps.append(2)

    catalog = get_catalog()
    _recompute_totals(draft, catalog, party=session.party)

    return {
        "draft_id": draft_id,
        "fare_package": package,
        "completed_steps": list(draft.completed_steps),
        "checkout_entry": checkout_entry(draft),
        "total": draft.total,
        "total_formatted": format_money(draft.total) if draft.total is not None else None,
        "total_delta": (draft.total or 0) - old_total,
    }


def set_stateroom(session: "Session", args: dict) -> dict:
    """
    Set the stateroom category and location on a draft and recompute totals.

    Args:
        session: current session
        args: {"draft_id": str, "category": str, "location": str|None}

    Returns:
        dict with updated draft info
    """
    from ..models import DraftStateroom

    draft_id = args.get("draft_id")
    category = args.get("category")
    location = args.get("location")

    draft = _find_draft(session, draft_id)
    if draft is None:
        return {"error": "draft_not_found", "message": f"Draft {draft_id!r} not found"}

    if not category:
        return {"error": "missing_category", "message": "category is required"}

    catalog = get_catalog()

    # Validate category against the catalog for this cruise (case-insensitive).
    # An invalid category must NOT price a delta, must NOT mark step 3, and must
    # NOT be stored on the draft.
    cruise_categories = [
        s.category for s in catalog["staterooms"] if s.cruise_id == draft.cruise_id
    ]
    match = next(
        (c for c in cruise_categories if c.lower() == category.lower()), None
    )
    if match is None:
        valid = ", ".join(cruise_categories)
        return {
            "error": "invalid_category",
            "message": f"Stateroom category {category!r} is not available for this cruise. Valid categories: {valid}.",
        }

    old_total = draft.total or 0
    # Store the canonical (catalog-cased) category.
    draft.stateroom = DraftStateroom(category=match, location=location)

    # Mark step 3
    if 3 not in draft.completed_steps:
        draft.completed_steps.append(3)

    _recompute_totals(draft, catalog, party=session.party)

    return {
        "draft_id": draft_id,
        "stateroom": {"category": match, "location": location},
        "completed_steps": list(draft.completed_steps),
        "checkout_entry": checkout_entry(draft),
        "total": draft.total,
        "total_formatted": format_money(draft.total) if draft.total is not None else None,
        "total_delta": (draft.total or 0) - old_total,
    }


def remove_draft(session: "Session", args: dict) -> dict:
    """
    Remove a draft from the session.

    Args:
        session: current session
        args: {"draft_id": str}

    Returns:
        dict with removed=True and remaining count, or {"error": "draft_not_found"}
    """
    draft_id = args.get("draft_id")
    if not draft_id:
        return {"error": "missing_draft_id", "message": "draft_id is required"}

    draft = _find_draft(session, draft_id)
    if draft is None:
        return {"error": "draft_not_found", "message": f"Draft {draft_id!r} not found"}

    session.drafts = [d for d in session.drafts if d.draft_id != draft_id]

    # Clear or reassign active_draft_id
    if session.active_draft_id == draft_id:
        session.active_draft_id = session.drafts[0].draft_id if session.drafts else None

    return {
        "removed": True,
        "draft_id": draft_id,
        "remaining": len(session.drafts),
    }


def set_sailing(session: "Session", args: dict) -> dict:
    """
    Update the sailing on an existing draft.

    Args:
        session: current session
        args: {"draft_id": str, "sailing_id": str}

    Returns:
        dict with updated sailing info, or error
    """
    draft_id = args.get("draft_id")
    sailing_id = args.get("sailing_id")

    if not draft_id:
        return {"error": "missing_draft_id", "message": "draft_id is required"}
    if not sailing_id:
        return {"error": "missing_sailing_id", "message": "sailing_id is required"}

    draft = _find_draft(session, draft_id)
    if draft is None:
        return {"error": "draft_not_found", "message": f"Draft {draft_id!r} not found"}

    catalog = get_catalog()
    cruise = next(
        (c for c in catalog["cruises"] if c.cruise_id == draft.cruise_id), None
    )
    if cruise is None:
        return {"error": "cruise_not_found", "message": f"Cruise {draft.cruise_id!r} not found"}

    sailing = next(
        (s for s in (cruise.sailings or []) if s.sailing_id == sailing_id), None
    )
    if sailing is None:
        return {
            "error": "sailing_not_found",
            "message": f"Sailing {sailing_id!r} not found for cruise {draft.cruise_id!r}",
        }

    draft.sailing_id = sailing.sailing_id
    draft.departure_date = sailing.departure_date
    draft.return_date = sailing.return_date

    return {
        "draft_id": draft_id,
        "sailing_id": sailing.sailing_id,
        "departure_date": sailing.departure_date,
        "return_date": sailing.return_date,
        "label": draft.label,
    }


def _find_draft(session: "Session", draft_id: Optional[str]) -> "Optional[Draft]":
    """Find a draft in session by ID."""
    if not draft_id:
        return None
    return next((d for d in session.drafts if d.draft_id == draft_id), None)


def disambiguate_drafts(session: "Session", args: dict) -> dict:
    """
    Return candidate draft summaries so the guest can pick between ambiguous drafts.

    Args:
        session: current session
        args: {"draft_ids": [str]} — optional; if absent or empty, use all session drafts

    Returns:
        dict with candidates list and active_draft_id
    """
    draft_ids = args.get("draft_ids") or []
    if draft_ids:
        candidates_drafts = [d for d in session.drafts if d.draft_id in draft_ids]
        # If no valid ids matched, fall back to all session drafts
        if not candidates_drafts:
            candidates_drafts = list(session.drafts)
    else:
        candidates_drafts = list(session.drafts)

    candidates = []
    for d in candidates_drafts:
        candidates.append({
            "draft_id": d.draft_id,
            "label": d.label,
            "region": None,  # enriched by caller if needed; basic version uses label
            "departure_date": d.departure_date,
            "return_date": d.return_date,
            "nights": None,
            "total_formatted": format_money(d.total) if d.total is not None else None,
        })

    # Enrich with region and nights from catalog
    from ..catalog.loader import get_catalog as _get_catalog
    catalog = _get_catalog()
    cruise_map = {c.cruise_id: c for c in catalog["cruises"]}
    for item in candidates:
        draft_obj = next((d for d in candidates_drafts if d.draft_id == item["draft_id"]), None)
        if draft_obj:
            cruise_obj = cruise_map.get(draft_obj.cruise_id)
            if cruise_obj:
                item["region"] = cruise_obj.region
                item["nights"] = cruise_obj.nights

    return {
        "candidates": candidates,
        "active_draft_id": session.active_draft_id,
    }
