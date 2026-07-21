"""
Compass — Gemini agentic loop client.

Uses the GA google-genai SDK (from google import genai).
Client is lazily created so tests can monkeypatch before first use.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable, Optional

from ..config import get_settings
from ..tools import TOOL_REGISTRY
from .. import observability
from .system_prompt import SYSTEM_PROMPT

MAX_STEPS = 10

# Module-level client — None until first use (lazy init allows test injection)
_client = None


def get_client():
    """Return the genai.Client, creating it lazily on first call."""
    global _client
    if _client is None:
        from google import genai  # noqa: PLC0415
        settings = get_settings()
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def set_client(client) -> None:
    """Inject a client (for testing / monkeypatching)."""
    global _client
    _client = client


def _build_tool():
    """Build a types.Tool containing FunctionDeclarations for every TOOL_REGISTRY entry."""
    from google.genai import types  # noqa: PLC0415

    declarations = []
    for name, (_, schema) in TOOL_REGISTRY.items():
        params = schema.get("parameters", {})
        declarations.append(
            types.FunctionDeclaration(
                name=name,
                description=schema.get("description", ""),
                parameters=params,
            )
        )
    return types.Tool(function_declarations=declarations)


def _build_config(tool: Any) -> Any:
    """Build GenerateContentConfig with tools and system instruction."""
    from google.genai import types  # noqa: PLC0415

    return types.GenerateContentConfig(
        tools=[tool],
        system_instruction=SYSTEM_PROMPT,
    )


def _map_tool_result_to_component(tool_name: str, result: dict) -> Optional[dict]:
    """Map a tool result dict to a UI component descriptor."""
    if "error" in result:
        return {"type": "error", "message": result["error"]}

    if tool_name == "search_cruises":
        cruises = result.get("cruises", [])
        filters = result.get("filters", {})
        # Limit to 5 cards
        cards = cruises[:5]
        return {"type": "card_row", "cards": cards, "filters": filters}

    if tool_name == "get_itinerary":
        return {"type": "itinerary", **result}

    if tool_name in ("create_draft", "set_fare", "set_stateroom"):
        draft = result.get("draft") or result
        return {"type": "tracker_update", "draft": draft}

    return None


def _parse_chips(text: str) -> tuple[str, list[str]]:
    """
    Extract CHIPS: [...] from the end of the model text.
    Returns (cleaned_text, chips_list).
    Falls back to [] if absent or malformed.
    """
    pattern = r'\nCHIPS:\s*(\[.*?\])\s*$'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        chips_json = match.group(1)
        clean_text = text[:match.start()].rstrip()
        try:
            chips = json.loads(chips_json)
            if isinstance(chips, list):
                return clean_text, chips
        except json.JSONDecodeError:
            pass
    return text, []


def _default_chips(tool_calls: list[str]) -> list[str]:
    """Return contextual default chips based on what tools were called."""
    if "search_cruises" in tool_calls:
        return ["Tell me more about the top result", "Show me Alaska cruises", "What's included?"]
    if "get_itinerary" in tool_calls:
        return ["Create a draft booking", "What are the dining options?", "Tell me about the ports"]
    if "create_draft" in tool_calls:
        return ["Upgrade my stateroom", "Choose fare package", "Add dining"]
    return ["Search for cruises", "Help me plan a trip", "What regions do you offer?"]


def run_turn(
    session,
    user_message: str,
    on_text_delta: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Run one conversational turn.

    Args:
        session: Session object from session_store
        user_message: The user's message text
        on_text_delta: Optional callback called with each streamed text chunk

    Returns:
        {text, components, chips, tool_calls}
    """
    from google.genai import types  # noqa: PLC0415

    t_turn_start = time.monotonic()

    client = get_client()
    tool = _build_tool()
    config = _build_config(tool)

    # Build conversation history from session.messages
    # system_event entries (appended by /action) are injected as user-role bracketed
    # notes so the model sees the result of tile taps on the next turn.
    contents = []
    for msg in session.messages:
        role = msg.get("role", "user")
        if role == "system_event":
            # Inject as a user-role note so Gemini sees state changes from tile taps
            event_text = msg.get("text", "")
            note = f"[system note: {event_text}]"
            contents.append(types.Content(role="user", parts=[types.Part(text=note)]))
        elif role in ("user", "model"):
            text = msg.get("content", "")
            contents.append(types.Content(role=role, parts=[types.Part(text=text)]))
        # else: skip unknown roles silently

    # Add current user message
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    components: list[dict] = []
    tool_calls_made: list[str] = []
    final_text = ""
    first_token_logged = False

    model_name = "gemini-2.0-flash"

    for step in range(MAX_STEPS):
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=config,
        )

        # Check if any part has a function call
        has_function_call = False
        function_calls_this_step = []

        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.function_call is not None:
                    has_function_call = True
                    function_calls_this_step.append(part.function_call)

        if has_function_call:
            # Append model turn with function calls
            model_parts = []
            for candidate in response.candidates:
                model_parts.extend(candidate.content.parts)
            contents.append(types.Content(role="model", parts=model_parts))

            # Execute each function call and build tool response parts
            tool_response_parts = []
            for fc in function_calls_this_step:
                tool_name = fc.name
                args = dict(fc.args) if fc.args else {}
                tool_calls_made.append(tool_name)

                t_start = time.monotonic()
                if tool_name in TOOL_REGISTRY:
                    handler, _ = TOOL_REGISTRY[tool_name]
                    try:
                        result = handler(session, args)
                    except Exception as exc:  # noqa: BLE001
                        result = {"error": str(exc)}
                else:
                    result = {"error": f"Unknown tool: {tool_name}"}

                latency_ms = int((time.monotonic() - t_start) * 1000)
                observability.record_tool_call(tool_name, latency_ms)

                # Map result to component descriptor
                component = _map_tool_result_to_component(tool_name, result)
                if component is not None:
                    components.append(component)

                tool_response_parts.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response=result,
                    )
                )

            # Append tool results as user turn
            contents.append(types.Content(role="user", parts=tool_response_parts))
            # Continue the loop
            continue

        else:
            # No function call — this is the final text response. Stream it.
            t_first_token = None

            # Use streaming for the final text turn
            stream = client.models.generate_content_stream(
                model=model_name,
                contents=contents,
                config=config,
            )

            text_chunks = []
            for chunk in stream:
                for candidate in chunk.candidates:
                    for part in candidate.content.parts:
                        if part.text:
                            if t_first_token is None:
                                t_first_token = time.monotonic()
                                if not first_token_logged:
                                    observability.record_first_token(t_turn_start)
                                    first_token_logged = True
                            text_chunks.append(part.text)
                            if on_text_delta:
                                on_text_delta(part.text)

            raw_text = "".join(text_chunks)
            final_text, chips = _parse_chips(raw_text)
            if not chips:
                chips = _default_chips(tool_calls_made)
            # Limit chips to 3
            chips = chips[:3]
            break

    else:
        # MAX_STEPS reached — safety fallback
        final_text = "I'm sorry, I wasn't able to complete that request. Please try again."
        chips = _default_chips(tool_calls_made)

    return {
        "text": final_text,
        "components": components,
        "chips": chips,
        "tool_calls": tool_calls_made,
    }
