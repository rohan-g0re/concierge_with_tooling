"""
Compass — POST /chat endpoint.

Returns a StreamingResponse (text/event-stream) with:
  event: text_delta
  data: {"delta": "..."}

  event: components
  data: {"components": [...], "chips": [...]}

Also persists the full turn to session.messages.
"""
from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..session_store import get_or_create, update
from ..llm.gemini_client import run_turn

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str
    message: str


async def _stream_turn(session_id: str, user_message: str) -> AsyncGenerator[str, None]:
    """
    Generator that yields SSE frames for a single chat turn.

    Yields text_delta events as text streams in, then a terminal
    components event with all components and chips.
    """
    session = get_or_create(session_id)

    # Collect deltas synchronously via callback, buffer them for SSE
    # Since run_turn is synchronous (wraps blocking Gemini calls), we call it
    # directly and collect deltas via the on_text_delta callback.
    # FastAPI will run this in a thread via StreamingResponse.
    # We use a list to buffer deltas that arrive during run_turn execution.
    delta_buffer: list[str] = []
    delta_index = [0]  # how many we've already yielded

    def on_delta(text: str) -> None:
        delta_buffer.append(text)

    # Run the turn (blocking call — runs in sync context)
    result = run_turn(session, user_message, on_text_delta=on_delta)

    # Yield all buffered text_delta events
    for delta in delta_buffer:
        frame = f"event: text_delta\ndata: {json.dumps({'delta': delta})}\n\n"
        yield frame

    # If no deltas were buffered but we have final text, yield it as one delta
    if not delta_buffer and result.get("text"):
        frame = f"event: text_delta\ndata: {json.dumps({'delta': result['text']})}\n\n"
        yield frame

    # Yield terminal components event
    terminal_data = {
        "components": result.get("components", []),
        "chips": result.get("chips", []),
    }
    yield f"event: components\ndata: {json.dumps(terminal_data)}\n\n"

    # Persist the turn to session messages
    session.messages.append({"role": "user", "content": user_message})
    session.messages.append({"role": "model", "content": result.get("text", "")})
    update(session)


@router.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    """
    Stream a Gemini-powered conversational turn over SSE.

    Body: {session_id: str, message: str}
    Response: text/event-stream with text_delta events then terminal components event.
    """
    if not req.session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not req.message:
        raise HTTPException(status_code=400, detail="message is required")

    return StreamingResponse(
        _stream_turn(req.session_id, req.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
