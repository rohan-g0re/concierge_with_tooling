"""
Compass — POST /feedback endpoint.

Logs thumbs up/down feedback to the observability ring buffer.
"""
from __future__ import annotations

from typing import Literal, Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..observability import _log_buffer

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackRequest(BaseModel):
    message_id: str
    vote: Literal["up", "down"]
    state_snapshot: dict[str, Any] = {}


@router.post("")
async def post_feedback(body: FeedbackRequest) -> dict:
    """Log a thumbs up/down vote for a message with optional state snapshot."""
    event = {
        "event": "feedback",
        "message_id": body.message_id,
        "vote": body.vote,
        "state_snapshot": body.state_snapshot,
    }
    _log_buffer.append(event)
    return {"ok": True, "message_id": body.message_id, "vote": body.vote}
