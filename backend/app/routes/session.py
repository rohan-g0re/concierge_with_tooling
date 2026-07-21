"""
Compass — GET /session/{session_id} endpoint.

Returns sanitized session state for frontend hydration.
Used by: DraftRail (P9), and later phases that need to read session state.

Response shape:
  {
    "session_id": str,
    "party": int,
    "active_draft_id": str | null,
    "drafts": [
      {
        "draft_id": str,
        "cruise_id": str,
        "label": str,
        "completed_steps": list[int],
        "total_formatted": str | null,
        "fare_package": str
      },
      ...
    ],
    "constraints": {
      "region": str | null,
      "nights_min": int | null,
      "nights_max": int | null,
      "embark_port": str | null,
      "budget_max": int | null,
      "party": int
    }
  }
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..session_store import get_or_create
from ..money import format_money

router = APIRouter()


@router.get("/session/{session_id}")
async def get_session(session_id: str) -> dict:
    """
    Return sanitized session state for frontend hydration.

    Creates the session if it doesn't exist yet (idempotent — same behavior
    as every other endpoint that calls get_or_create).
    """
    session = get_or_create(session_id)

    from ..catalog.loader import get_catalog
    from ..money import draft_total
    catalog = get_catalog()
    cruise_map = {c.cruise_id: c for c in catalog["cruises"]}

    drafts = []
    for draft in session.drafts:
        if draft.total is not None:
            deposit = round(draft.total * 0.20)
            balance = draft.total - deposit
            deposit_formatted = format_money(deposit)
            balance_formatted = format_money(balance)
        else:
            deposit_formatted = None
            balance_formatted = None

        cruise = cruise_map.get(draft.cruise_id)
        region = cruise.region if cruise else None
        embark_port = cruise.embark_port if cruise else None
        nights = cruise.nights if cruise else None

        # addons_note: "includes US$ NNN add-ons" when add-ons delta > 0 and draft has dates
        addons_note = None
        if draft.total is not None and cruise is not None and draft.departure_date is not None:
            base_fare_total = cruise.fare_now * session.party
            addon_delta = draft.total - base_fare_total
            if addon_delta > 0:
                addons_note = f"includes {format_money(addon_delta)} add-ons"

        drafts.append({
            "draft_id": draft.draft_id,
            "cruise_id": draft.cruise_id,
            "label": draft.label,
            "completed_steps": list(draft.completed_steps),
            "total_formatted": format_money(draft.total) if draft.total is not None else None,
            "fare_package": draft.fare_package,
            "deposit_formatted": deposit_formatted,
            "balance_formatted": balance_formatted,
            "region": region,
            "embark_port": embark_port,
            "departure_date": draft.departure_date,
            "return_date": draft.return_date,
            "nights": nights,
            "addons_note": addons_note,
        })

    return {
        "session_id": session.session_id,
        "party": session.party,
        "active_draft_id": session.active_draft_id,
        "drafts": drafts,
        "constraints": {
            "region": session.constraints.region,
            "nights_min": session.constraints.nights_min,
            "nights_max": session.constraints.nights_max,
            "embark_port": session.constraints.embark_port,
            "budget_max": session.constraints.budget_max,
            "party": session.constraints.party,
        },
    }


@router.get("/session/{session_id}/draft/{draft_id}/step/{step}/options")
async def get_step_options(session_id: str, draft_id: str, step: int) -> dict:
    """
    Return the SAME component descriptors a fresh /action chain would emit for a
    given draft + booking step, so the checkout resume page can render identical,
    editable UI inline (R21 single-source parity — descriptors come from the exact
    helper functions used by the /action route).

    Steps:
      2 → fare_tiles     (with the draft's current_package pre-selected)
      3 → stateroom_picker
      4 → dining_tiles (+ land_builder for cruisetours)

    Response: {"draft_id": str, "step": int, "components": [<descriptor>, ...]}

    Errors:
      404 session_not_found / draft_not_found
      400 unsupported_step
    """
    # Import the shared descriptor builders from the action route so there is a
    # single source of truth for component shapes (R21).
    from .action import (
        _fare_tiles_options,
        _append_stateroom_picker,
        _append_dining_tiles,
        _append_land_builder,
    )

    session = get_or_create(session_id)
    draft = next((d for d in session.drafts if d.draft_id == draft_id), None)
    if draft is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "draft_not_found", "message": f"Draft {draft_id!r} not found"},
        )

    if step not in (2, 3, 4):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unsupported_step",
                "message": f"Step {step} has no inline-editable options (supported: 2, 3, 4).",
            },
        )

    components: list[dict] = []

    if step == 2:
        # Fare — mirror the fare_tiles descriptor the create_draft chain emits,
        # pre-selecting the draft's current package so the component initializes
        # to the saved choice.
        components.append({
            "type": "fare_tiles",
            "draft_id": draft_id,
            "options": _fare_tiles_options(),
            "current_package": draft.fare_package,
        })

    elif step == 3:
        # Stateroom — identical to the set_fare chain.
        _append_stateroom_picker(components, {"draft_id": draft_id}, session)

    elif step == 4:
        # Add-ons — dining always; land builder only for cruisetours.
        _append_dining_tiles(components, draft_id, session)
        _append_land_builder(components, draft_id, session)

    return {"draft_id": draft_id, "step": step, "components": components}
