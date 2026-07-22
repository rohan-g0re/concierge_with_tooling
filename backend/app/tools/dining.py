"""
Compass — Dining tools: list_dining, reserve_dining.

Capacity tracking is per-session overlay — the shared catalog singleton is
never mutated.  Overlays are stored in a module-level dict keyed by session_id:
  _session_overlays: {session_id: {cruise_id: {venue_id: {night: remaining}}}}
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..catalog.loader import get_catalog
from ..money import draft_total, format_money

if TYPE_CHECKING:
    from ..models import Session, Draft

# Module-level capacity overlay storage: session_id → cruise_id → venue_id → night → remaining
_session_overlays: dict[str, dict] = {}


def _get_overlay(session: "Session") -> dict:
    """Return (or lazily create) the session-scoped capacity overlay dict."""
    sid = session.session_id
    if sid not in _session_overlays:
        _session_overlays[sid] = {}
    return _session_overlays[sid]


def _capacity_for(session: "Session", cruise_id: str, venue_id: str, night: int, catalog_venues: list) -> int:
    """Return effective remaining capacity for (cruise_id, venue_id, night)."""
    overlay = _get_overlay(session)
    try:
        return overlay[cruise_id][venue_id][night]
    except KeyError:
        pass
    # Fall back to catalog value
    for venue in catalog_venues:
        if venue.cruise_id == cruise_id and venue.venue_id == venue_id:
            for vn in venue.nights:
                if vn.night == night:
                    return vn.capacity_remaining
    return 0


def _decrement_capacity(session: "Session", cruise_id: str, venue_id: str, night: int, catalog_venues: list) -> None:
    """Decrement capacity in the session overlay (never mutating catalog)."""
    current = _capacity_for(session, cruise_id, venue_id, night, catalog_venues)
    overlay = _get_overlay(session)
    overlay.setdefault(cruise_id, {}).setdefault(venue_id, {})[night] = max(0, current - 1)


def _find_draft(session: "Session", draft_id: str):
    """Find draft in session by id."""
    return next((d for d in session.drafts if d.draft_id == draft_id), None)


def _recompute_totals(draft: "Draft", catalog: dict, party: int) -> None:
    total = draft_total(draft, catalog, party=party)
    draft.total = total
    draft.total_per_person = total // party if party > 0 else total


def list_dining(session: "Session", args: dict) -> dict:
    """
    List dining venues for a cruise with per-night availability grid.

    Args:
        session: current session
        args: {"cruise_id": str}

    Returns:
        dict with "venues" list, each venue having:
          - venue_id, name, cuisine, price_per_guest, price_formatted
          - nights: list of {night, status: available|reserved|sold_out}
    """
    cruise_id = args.get("cruise_id")
    if not cruise_id:
        return {"error": "missing_cruise_id", "message": "cruise_id is required"}

    catalog = get_catalog()

    # Verify cruise exists
    cruise = next((c for c in catalog["cruises"] if c.cruise_id == cruise_id), None)
    if cruise is None:
        return {"error": "cruise_not_found", "message": f"Cruise {cruise_id!r} not found"}

    catalog_venues = [v for v in catalog["dining"] if v.cruise_id == cruise_id]

    # Collect all reservations already in any draft in this session for this cruise
    # so we can mark "reserved" nights per venue.
    # reserved = this session's drafts already hold it (capacity decremented via overlay).
    all_draft_dining: set[str] = set()
    for d in session.drafts:
        if d.cruise_id == cruise_id:
            for sel in d.dining:
                all_draft_dining.add(sel)  # "venue_id:night_N"

    result_venues = []
    for venue in catalog_venues:
        nights_grid = []
        for vn in venue.nights:
            night = vn.night
            key = f"{venue.venue_id}:night_{night}"
            capacity = _capacity_for(session, cruise_id, venue.venue_id, night, catalog_venues)
            if capacity == 0:
                status = "sold_out"
            elif key in all_draft_dining:
                status = "reserved"
            else:
                status = "available"
            nights_grid.append({"night": night, "status": status})

        result_venues.append({
            "venue_id": venue.venue_id,
            "name": venue.name,
            "cuisine": venue.cuisine,
            "price_per_guest": venue.price_per_guest,
            "price_formatted": format_money(venue.price_per_guest),
            "nights": nights_grid,
        })

    return {"cruise_id": cruise_id, "venues": result_venues}


def reserve_dining(session: "Session", args: dict) -> dict:
    """
    Reserve a dining venue for a specific night on a draft.

    Args:
        session: current session
        args: {"draft_id": str, "venue_id": str, "night": int}

    Returns:
        dict with updated draft info, or structured error dict.
    """
    draft_id = args.get("draft_id")
    venue_id = args.get("venue_id")
    night = args.get("night")

    if not draft_id:
        return {"error": "missing_draft_id", "message": "draft_id is required"}
    if not venue_id:
        return {"error": "missing_venue_id", "message": "venue_id is required"}
    if night is None:
        return {"error": "missing_night", "message": "night is required"}

    draft = _find_draft(session, draft_id)
    if draft is None:
        return {"error": "draft_not_found", "message": f"Draft {draft_id!r} not found"}

    catalog = get_catalog()
    catalog_venues = [v for v in catalog["dining"] if v.cruise_id == draft.cruise_id]

    # Verify venue exists for this cruise
    venue = next((v for v in catalog_venues if v.venue_id == venue_id), None)
    if venue is None:
        return {"error": "venue_not_found", "message": f"Venue {venue_id!r} not found for cruise {draft.cruise_id!r}"}

    # Verify night exists in venue
    night_record = next((vn for vn in venue.nights if vn.night == night), None)
    if night_record is None:
        return {"error": "night_not_found", "message": f"Night {night} not found for venue {venue_id!r}"}

    # Check sold out (using session overlay)
    capacity = _capacity_for(session, draft.cruise_id, venue_id, night, catalog_venues)
    if capacity == 0:
        return {
            "error": "sold_out",
            "message": "Fully reserved this night",
        }

    # Check double-book: same (venue, night) already in this draft
    selection_key = f"{venue_id}:night_{night}"
    if selection_key in draft.dining:
        return {
            "error": "double_book",
            "message": f"You have already reserved {venue_id!r} for night {night} in this draft.",
        }

    # Success: append reservation, decrement capacity, recompute totals, mark step 4
    draft.dining.append(selection_key)
    _decrement_capacity(session, draft.cruise_id, venue_id, night, catalog_venues)

    if 4 not in draft.completed_steps:
        draft.completed_steps.append(4)

    _recompute_totals(draft, catalog, party=session.party)

    return {
        "draft_id": draft_id,
        "venue_id": venue_id,
        "night": night,
        "selection_key": selection_key,
        "dining": list(draft.dining),
        "completed_steps": list(draft.completed_steps),
        "total": draft.total,
        "total_formatted": format_money(draft.total) if draft.total is not None else None,
    }


def set_dining_time(session: "Session", args: dict) -> dict:
    """
    Set a preferred dining time for main dining on a draft.

    This is an /action-only tool (NOT registered in Gemini tool declarations).
    Stores the preference on draft.dining_time_pref.

    Args:
        session: current session
        args: {"draft_id": str, "time_slot": str}
              time_slot one of: "early" (5:30 PM), "main" (7:30 PM), "late" (9:00 PM)

    Returns:
        dict with draft_id, time_slot, time_label
    """
    draft_id = args.get("draft_id")
    time_slot = args.get("time_slot")

    if not draft_id:
        return {"error": "missing_draft_id", "message": "draft_id is required"}
    if not time_slot:
        return {"error": "missing_time_slot", "message": "time_slot is required"}

    _TIME_LABELS = {
        "early": "5:30 PM",
        "main": "7:30 PM",
        "late": "9:00 PM",
    }

    if time_slot not in _TIME_LABELS:
        return {
            "error": "invalid_time_slot",
            "message": f"time_slot must be one of: {', '.join(_TIME_LABELS)}",
        }

    draft = _find_draft(session, draft_id)
    if draft is None:
        return {"error": "draft_not_found", "message": f"Draft {draft_id!r} not found"}

    draft.dining_time_pref = time_slot

    return {
        "draft_id": draft_id,
        "time_slot": time_slot,
        "time_label": _TIME_LABELS[time_slot],
    }
