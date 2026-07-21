"""
Compass — POST /voice/token endpoint.

Mints an ephemeral OpenAI Realtime session token so the browser can connect
directly to the Realtime API without ever seeing the standing OPENAI_API_KEY.

Key detection:
  OPENAI_API_KEY is treated as *unset* when it is empty OR starts with "your_"
  (placeholder value). In that case the endpoint returns a structured
  "voice_unavailable" state instead of crashing.

Token shape (real key):
  {
    "available": true,
    "client_secret": { "value": "<ephemeral_token>", "expires_at": <unix_ts> },
    "model": "gpt-4o-realtime-preview-2024-12-17",
    "voice": "alloy",
    "tools": [ <openai-format tool schemas from TOOL_REGISTRY> ]
  }

Unavailable shape (missing/placeholder key):
  {
    "available": false,
    "reason": "voice_unavailable",
    "message": "Voice is not configured. Please ask your concierge by typing."
  }

R21 parity note:
  The `tools` array is built from TOOL_REGISTRY so voice and tap share the
  same schemas. Voice tool calls are relayed through POST /action/{tool} by
  the frontend voiceClient, so handlers are never duplicated.
"""
from __future__ import annotations

import httpx

from fastapi import APIRouter

from ..config import get_settings
from ..tools import TOOL_REGISTRY

router = APIRouter()

_REALTIME_SESSIONS_URL = "https://api.openai.com/v1/realtime/sessions"
_REALTIME_MODEL = "gpt-4o-realtime-preview-2024-12-17"
_REALTIME_VOICE = "alloy"

UNAVAILABLE_RESPONSE = {
    "available": False,
    "reason": "voice_unavailable",
    "message": "Voice is not configured. Please ask your concierge by typing.",
}


def _key_is_set(key: str) -> bool:
    """Return True iff the key is non-empty and not a placeholder."""
    return bool(key) and not key.startswith("your_")


def _build_realtime_tools() -> list[dict]:
    """
    Convert TOOL_REGISTRY schemas to OpenAI Realtime tool format.

    OpenAI Realtime tool shape:
      {
        "type": "function",
        "name": "<name>",
        "description": "<description>",
        "parameters": { <JSON Schema object> }
      }
    """
    tools = []
    for tool_name, (_handler, schema) in TOOL_REGISTRY.items():
        tools.append({
            "type": "function",
            "name": tool_name,
            "description": schema.get("description", ""),
            "parameters": schema.get("parameters", {}),
        })
    return tools


@router.post("/voice/token")
async def voice_token() -> dict:
    """
    Mint an ephemeral OpenAI Realtime session token.

    Returns voice_unavailable state if OPENAI_API_KEY is missing or placeholder.
    Otherwise calls the OpenAI Realtime sessions API and returns the token.

    The ephemeral token is short-lived (typically 60s) and scoped only to the
    Realtime API — the standing key is never sent to the browser.
    """
    settings = get_settings()
    api_key = settings.openai_api_key

    if not _key_is_set(api_key):
        return UNAVAILABLE_RESPONSE

    realtime_tools = _build_realtime_tools()

    payload = {
        "model": _REALTIME_MODEL,
        "voice": _REALTIME_VOICE,
        "tools": realtime_tools,
        "instructions": (
            "You are Compass, a conversational cruise concierge for Carnival and HAL. "
            "Help guests plan their cruise vacation. When you call a tool, call it once "
            "and give a spoken summary of the result in 2 sentences or fewer — the visual "
            "cards on screen show full detail. Be warm, concise, and helpful."
        ),
        "turn_detection": {"type": "server_vad"},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            _REALTIME_SESSIONS_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    # Extract the ephemeral token fields
    client_secret = data.get("client_secret", {})
    return {
        "available": True,
        "client_secret": client_secret,
        "model": _REALTIME_MODEL,
        "voice": _REALTIME_VOICE,
        "tools": realtime_tools,
    }
