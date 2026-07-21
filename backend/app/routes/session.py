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

    drafts = []
    for draft in session.drafts:
        drafts.append({
            "draft_id": draft.draft_id,
            "cruise_id": draft.cruise_id,
            "label": draft.label,
            "completed_steps": list(draft.completed_steps),
            "total_formatted": format_money(draft.total) if draft.total is not None else None,
            "fare_package": draft.fare_package,
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
