"""
Compass — compare_drafts tool.

Produces aligned comparison rows from customized drafts (not base products).
Row keys match design compareRows exactly. Max 3 drafts enforced.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Session

from ..catalog.loader import get_catalog
from ..money import draft_total, format_money

_MAX_COMPARE = 3

# Fare package display names (UI names per plan A1)
_FARE_DISPLAY = {
    "have_it_all": "The Signature Collection",
    "good_to_go": "Standard",
}

# Deposit terms by fare package
_DEPOSIT_TERMS = {
    "have_it_all": "US$ 700 · refundable 30 days",
    "good_to_go": "US$ 500 · refundable 30 days",
}


def compare_drafts(session: "Session", args: dict) -> dict:
    """
    Build aligned comparison rows from customized drafts.

    Args:
        session: current session
        args: {"draft_ids": list[str]}

    Returns:
        dict with "rows" (list of {label, values[], differ:bool}),
        "headers" (per-draft info), and "checkout_urls".
        On error: {"error": "compare_cap", "message": "...up to three..."}
    """
    raw_ids = args.get("draft_ids") or []

    # Cap check fires first, on the caller's explicit request.
    if len(raw_ids) > _MAX_COMPARE:
        return {
            "error": "compare_cap",
            "message": f"Comparison supports up to three drafts at a time. Please select up to 3 drafts to compare.",
        }

    session_ids = [d.draft_id for d in session.drafts]

    # Defense in depth: the live model may pass hallucinated / stale ids, or
    # none at all. Filter the requested ids to those that actually exist in the
    # session. If fewer than 2 valid ids survive, fall back to *all* session
    # drafts (capped at 3) so "compare my drafts" still works without the model
    # needing to know exact ids.
    valid_ids = [did for did in raw_ids if did in session_ids]
    if len(valid_ids) < 2:
        valid_ids = session_ids[:_MAX_COMPARE]

    # Even after fallback, we need at least 2 drafts to compare.
    if len(valid_ids) < 2:
        return {
            "error": "no_drafts",
            "message": "You'll need at least two drafts to compare. Create a second draft and I'll line them up side by side.",
        }

    # Resolve drafts from session (all ids here are known to exist)
    drafts = []
    for did in valid_ids:
        d = next((d for d in session.drafts if d.draft_id == did), None)
        if d is not None:
            drafts.append(d)

    catalog = get_catalog()
    party = session.party

    # Build per-draft data
    draft_data = []
    for draft in drafts:
        cruise = next((c for c in catalog["cruises"] if c.cruise_id == draft.cruise_id), None)
        if cruise is None:
            return {"error": "cruise_not_found", "message": f"Cruise {draft.cruise_id!r} not found."}

        # Compute totals
        total = draft_total(draft, catalog, party=party)
        per_person = total // party if party > 0 else total

        # Dates
        dates = f"{cruise.name}"  # fallback; real dates not in model, use cruise name as label
        # The cruise model doesn't have embarkation date fields, so we use the cruise name
        # and identify "Dates" from the draft label. Design shows "Jun 14 – Jun 26, 2027" etc.
        # Since dates aren't stored in the model, we emit the cruise name as the date label.
        # For diff purposes: two drafts on the same cruise_id have same dates.

        # Stateroom label
        stateroom_label = draft.stateroom.category
        if draft.stateroom.location:
            stateroom_label += f" · {draft.stateroom.location}"

        # Dining reserved
        if draft.dining:
            # dining entries are "venue_id:night_N"
            dining_parts = []
            venue_map = {v.venue_id: v for v in catalog["dining"] if v.cruise_id == draft.cruise_id}
            for sel in draft.dining:
                parts = sel.split(":")
                vid = parts[0]
                night_part = parts[1] if len(parts) > 1 else ""
                vname = venue_map[vid].name if vid in venue_map else vid
                night_num = night_part.replace("night_", "Night ") if night_part else ""
                dining_parts.append(f"{vname} · {night_num}" if night_num else vname)
            dining_label = ", ".join(dining_parts)
        else:
            dining_label = "None yet"

        # Land days
        if draft.land_days:
            land_map = {o.option_id: o for o in catalog["land"] if o.cruise_id == draft.cruise_id}
            land_names = []
            for ld in draft.land_days:
                opt = land_map.get(ld.option_id)
                if opt:
                    land_names.append(opt.name)
            land_label = f"{len(draft.land_days)} · {', '.join(land_names)}" if land_names else f"{len(draft.land_days)} days"
        else:
            land_label = "—"

        # Nights label (cruisetour shows sea + land)
        if cruise.is_cruisetour and draft.land_days:
            land_count = len(draft.land_days)
            sea_nights = cruise.nights - land_count
            nights_label = f"{cruise.nights} ({sea_nights} sea + {land_count} land)"
        else:
            nights_label = str(cruise.nights)

        draft_data.append({
            "draft": draft,
            "cruise": cruise,
            "dates": cruise.name,  # proxy for dates (no date field in model)
            "nights": nights_label,
            "ship": cruise.ship,
            "fare_package": _FARE_DISPLAY.get(draft.fare_package, draft.fare_package),
            "stateroom": stateroom_label,
            "dining": dining_label,
            "land_days": land_label,
            "per_person": format_money(per_person),
            "total": format_money(total),
            "total_raw": total,
            "per_person_raw": per_person,
            "deposit_terms": _DEPOSIT_TERMS.get(draft.fare_package, "US$ 500 · refundable 30 days"),
        })

    # Build aligned rows with differ flags
    def _row(label: str, key: str) -> dict:
        values = [dd[key] for dd in draft_data]
        differ = len(set(values)) > 1
        return {"label": label, "values": values, "differ": differ}

    rows = [
        _row("Dates", "dates"),
        _row("Nights", "nights"),
        _row("Ship", "ship"),
        _row("Fare package", "fare_package"),
        _row("Stateroom", "stateroom"),
        _row("Dining reserved", "dining"),
        _row("Land days", "land_days"),
        _row("Per person", "per_person"),
        {"label": f"Total · {party} guests", "values": [dd["total"] for dd in draft_data], "differ": len(set(dd["total_raw"] for dd in draft_data)) > 1},
        _row("Deposit terms", "deposit_terms"),
    ]

    # Per-draft headers
    headers = [
        {
            "draft_id": dd["draft"].draft_id,
            "label": dd["draft"].label,
            "ship": dd["cruise"].ship,
            "photo": dd["cruise"].photo,
        }
        for dd in draft_data
    ]

    checkout_urls = [f"/checkout/{dd['draft'].draft_id}" for dd in draft_data]

    return {
        "rows": rows,
        "headers": headers,
        "checkout_urls": checkout_urls,
        "party": party,
    }
