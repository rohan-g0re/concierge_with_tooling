"""
Compass — handoff_checkout tool.

Returns a checkout URL for a given draft_id.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Session


def handoff_checkout(session: "Session", args: dict) -> dict:
    """
    Return the checkout URL for a draft.

    Args:
        session: current session
        args: {"draft_id": str}

    Returns:
        {"url": "/checkout/<draft_id>"} or {"error": "draft_not_found", "message": ...}
    """
    draft_id = args.get("draft_id")
    if not draft_id:
        return {"error": "missing_draft_id", "message": "draft_id is required."}

    draft = next((d for d in session.drafts if d.draft_id == draft_id), None)
    if draft is None:
        return {"error": "draft_not_found", "message": f"Draft {draft_id!r} not found in session."}

    return {"url": f"/checkout/{draft_id}?session={session.session_id}"}
