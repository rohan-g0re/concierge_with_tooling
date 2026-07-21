"""
Compass — GET /debug endpoint.

Returns live session state: constraints, drafts, active_draft,
recent messages, and the tool-call log with latencies from the
observability ring buffer.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..session_store import get_or_create
from ..observability import get_log

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("")
async def get_debug(session_id: str = Query(default="demo")) -> dict:
    """Return sanitized live session state + observability log."""
    session = get_or_create(session_id)

    # Build a safe session snapshot (no raw LLM messages — just metadata)
    drafts_summary = []
    for d in session.drafts:
        drafts_summary.append({
            "draft_id": d.draft_id,
            "label": d.label,
            "fare_package": d.fare_package,
            "stateroom": d.stateroom.model_dump() if d.stateroom else None,
            "dining": d.dining,
            "completed_steps": d.completed_steps,
            "total_per_person": d.total_per_person,
        })

    # Recent messages — strip content to just role + id for safety
    messages_meta = [
        {"role": m.get("role"), "id": m.get("id"), "ts": m.get("ts")}
        for m in session.messages[-20:]
    ]

    # Tool-call log from ring buffer
    tool_log = [e for e in get_log() if e.get("event") in ("tool_call", "first_token", "feedback")]

    return {
        "session_id": session_id,
        "constraints": session.constraints.model_dump(),
        "party": session.party,
        "active_draft_id": session.active_draft_id,
        "drafts": drafts_summary,
        "messages_count": len(session.messages),
        "messages_meta": messages_meta,
        "tool_log": tool_log[-50:],  # last 50 events
    }
