"""
Compass — Land-tour tools: list_land_options, set_land_days.

Only cruisetours have land options. Conflict validation is server-side;
no catalog mutation occurs.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..catalog.loader import get_catalog
from ..money import draft_total, format_money

if TYPE_CHECKING:
    from ..models import Session, Draft


def _find_draft(session: "Session", draft_id: str):
    return next((d for d in session.drafts if d.draft_id == draft_id), None)


def _recompute_totals(draft: "Draft", catalog: dict, party: int) -> None:
    total = draft_total(draft, catalog, party=party)
    draft.total = total
    draft.total_per_person = total // party if party > 0 else total


def list_land_options(session: "Session", args: dict) -> dict:
    """
    List land-tour options for a cruisetour cruise.

    Args:
        session: current session
        args: {"cruise_id": str}

    Returns:
        dict with "options" list, or structured error if cruise is not a cruisetour.
    """
    cruise_id = args.get("cruise_id")
    if not cruise_id:
        return {"error": "missing_cruise_id", "message": "cruise_id is required"}

    catalog = get_catalog()

    cruise = next((c for c in catalog["cruises"] if c.cruise_id == cruise_id), None)
    if cruise is None:
        return {"error": "cruise_not_found", "message": f"Cruise {cruise_id!r} not found"}

    if not cruise.is_cruisetour:
        return {
            "error": "not_cruisetour",
            "message": f"Cruise {cruise_id!r} is not a cruisetour. Land options are only available for cruisetour itineraries.",
            "options": [],
        }

    land_options = [o for o in catalog["land"] if o.cruise_id == cruise_id]

    result_options = []
    for opt in land_options:
        result_options.append({
            "option_id": opt.option_id,
            "day": opt.day,
            "name": opt.name,
            "description": opt.description,
            "price_per_guest": opt.price_per_guest,
            "price_formatted": format_money(opt.price_per_guest),
            "conflicts_with": list(opt.conflicts_with),
            "conflict_reason": opt.conflict_reason,
        })

    return {"cruise_id": cruise_id, "options": result_options}


def set_land_days(session: "Session", args: dict) -> dict:
    """
    Set land-day selections on a draft, with conflict and duplicate-day validation.

    Args:
        session: current session
        args: {"draft_id": str, "option_ids": list[str]}

    Returns:
        dict with updated draft info, or structured error dict.
    """
    from ..models import DraftLandDay

    draft_id = args.get("draft_id")
    option_ids = args.get("option_ids")

    if not draft_id:
        return {"error": "missing_draft_id", "message": "draft_id is required"}
    if option_ids is None:
        return {"error": "missing_option_ids", "message": "option_ids is required"}

    draft = _find_draft(session, draft_id)
    if draft is None:
        return {"error": "draft_not_found", "message": f"Draft {draft_id!r} not found"}

    catalog = get_catalog()

    cruise = next((c for c in catalog["cruises"] if c.cruise_id == draft.cruise_id), None)
    if cruise is None:
        return {"error": "cruise_not_found", "message": f"Cruise {draft.cruise_id!r} not found"}

    if not cruise.is_cruisetour:
        return {
            "error": "not_cruisetour",
            "message": f"Cruise {draft.cruise_id!r} is not a cruisetour. Land options are only available for cruisetour itineraries.",
        }

    land_options = [o for o in catalog["land"] if o.cruise_id == draft.cruise_id]
    land_map = {o.option_id: o for o in land_options}

    # Validate all option_ids exist
    for oid in option_ids:
        if oid not in land_map:
            return {
                "error": "unknown_option",
                "message": f"Land option {oid!r} not found for cruise {draft.cruise_id!r}",
            }

    # Check for conflicting pairs
    option_ids_set = set(option_ids)
    for oid in option_ids:
        opt = land_map[oid]
        for conflicting_id in opt.conflicts_with:
            if conflicting_id in option_ids_set:
                # Use the conflict_reason from the option that declares the conflict
                reason = opt.conflict_reason or f"Conflicts with {conflicting_id}"
                return {
                    "error": "conflict",
                    "reason": reason,
                }

    # Check for duplicate days (two options on same day)
    seen_days: dict[int, str] = {}
    for oid in option_ids:
        opt = land_map[oid]
        day = opt.day
        if day in seen_days:
            return {
                "error": "duplicate_day",
                "message": f"Options {seen_days[day]!r} and {oid!r} are both on Day {day}. Only one option per day is allowed.",
            }
        seen_days[day] = oid

    # Success: store land_days on draft, recompute totals, mark step 4
    draft.land_days = [DraftLandDay(day=land_map[oid].day, option_id=oid) for oid in option_ids]

    if 4 not in draft.completed_steps:
        draft.completed_steps.append(4)

    _recompute_totals(draft, catalog, party=session.party)

    return {
        "draft_id": draft_id,
        "land_days": [{"day": ld.day, "option_id": ld.option_id} for ld in draft.land_days],
        "completed_steps": list(draft.completed_steps),
        "total": draft.total,
        "total_formatted": format_money(draft.total) if draft.total is not None else None,
    }
