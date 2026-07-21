"""
Compass — Stub LLM orchestrator (no API key required).

Deterministic keyword-based run_turn with the same signature as gemini_client.run_turn.
Used when llm_mode='stub' or when no GEMINI_API_KEY is configured (llm_mode='auto').
"""
from __future__ import annotations

import re
from typing import Callable

from ..tools import TOOL_REGISTRY


def run_turn(session, user_message: str, on_text_delta: Callable[[str], None] | None = None) -> dict:
    """
    Deterministic keyword-based run_turn.

    Returns {"text": str, "components": list, "chips": list, "tool_calls": list}
    """
    msg = user_message.lower()

    # --- Cruise search branch ---
    if any(kw in msg for kw in ("alaska", "mexico", "caribbean", "mediterranean", "cruise", "sail", "voyage")):
        args: dict = {}

        # region
        for region in ("alaska", "mexico", "caribbean", "mediterranean"):
            if region in msg:
                args["region"] = region
                break

        # nights_min / nights_max
        range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*day", msg)
        single_match = re.search(r"(\d+)\s*day", msg)
        if "two-week" in msg or "14 day" in msg or "14-day" in msg:
            args["nights_min"] = 14
            args["nights_max"] = 14
        elif "7 day" in msg or "7-day" in msg:
            args["nights_min"] = 7
            args["nights_max"] = 7
        elif range_match:
            args["nights_min"] = int(range_match.group(1))
            args["nights_max"] = int(range_match.group(2))
        elif single_match:
            args["nights_min"] = int(single_match.group(1))

        # embark_port: "from <word>"
        port_match = re.search(r"\bfrom\s+([a-z]+)", msg)
        if port_match:
            args["embark_port"] = port_match.group(1)

        # budget_max: "under $N" or "under $N,NNN"
        budget_match = re.search(r"under\s+\$([0-9,]+)", msg)
        if budget_match:
            args["budget_max"] = int(budget_match.group(1).replace(",", ""))

        result = TOOL_REGISTRY["search_cruises"][0](session, args)

        preamble_1 = "I found some great options for you."
        preamble_2 = " Here's what matches your request:"
        if on_text_delta:
            on_text_delta(preamble_1)
            on_text_delta(preamble_2)
        text = preamble_1 + preamble_2

        components = [
            {
                "type": "card_row",
                "cards": result.get("results", [])[:5],
                "filters": result.get("filters", {}),
            },
            {
                "type": "system_event",
                "tool_calls": ["search_cruises"],
                "filters": result.get("filters", {}),
            },
        ]
        chips = ["Tell me more about the top result", "Create a draft booking", "What's included?"]
        return {"text": text, "components": components, "chips": chips, "tool_calls": ["search_cruises"]}

    # --- Itinerary branch ---
    elif any(kw in msg for kw in ("itinerary", "ports", "days at sea")):
        cruise_id_match = re.search(r"\b[a-z]{2}-\d{3}\b", msg)
        if cruise_id_match:
            cruise_id = cruise_id_match.group(0)
        elif session.constraints and hasattr(session.constraints, "__iter__"):
            # try to get first cruise from constraints
            try:
                cruise_id = session.constraints[0] if session.constraints else "al-001"
            except (TypeError, IndexError):
                cruise_id = "al-001"
        else:
            cruise_id = "al-001"

        result = TOOL_REGISTRY["get_itinerary"][0](session, {"cruise_id": cruise_id})

        preamble = "Here's the day-by-day itinerary for your cruise."
        if on_text_delta:
            on_text_delta(preamble)
        text = preamble

        components = [{"type": "itinerary", **result}]
        chips = ["Create a draft booking", "What are the dining options?", "Tell me about the ports"]
        return {"text": text, "components": components, "chips": chips, "tool_calls": ["get_itinerary"]}

    # --- Compare branch ---
    elif "compare" in msg:
        draft_ids = [d.draft_id for d in session.drafts] if session.drafts else []
        if len(draft_ids) >= 2:
            result = TOOL_REGISTRY["compare_drafts"][0](session, {"draft_ids": draft_ids[:3]})
            text = ""
            components = [{"type": "comparison", **result}]
        else:
            text = "You need at least two drafts to compare. Try creating a draft first."
            if on_text_delta:
                on_text_delta(text)
            components = []
        chips = ["Create a draft", "Search for more cruises", "Continue to checkout"]
        return {"text": text, "components": components, "chips": chips, "tool_calls": []}

    # --- Draft/booking branch ---
    elif any(kw in msg for kw in ("total", "my draft", "booking", "draft")):
        if session.drafts:
            from ..money import format_money
            draft = session.drafts[0]
            total = draft.total
            text = f"Your current draft: {draft.draft_id}. Total: {format_money(total) if total is not None else 'not yet calculated'}."
        else:
            text = "You don't have any active drafts yet. Search for a cruise to get started."
        if on_text_delta:
            on_text_delta(text)
        components = []
        chips = ["Choose fare package", "Select stateroom", "Compare my drafts"]
        return {"text": text, "components": components, "chips": chips, "tool_calls": []}

    # --- Off-scope branch ---
    elif any(kw in msg for kw in ("wifi", "password", "weather", "visa", "flight", "hotel", "refund", "cancel")):
        text = "I'm focused on cruise planning — for that question, please contact our support team."
        if on_text_delta:
            on_text_delta(text)
        components = []
        chips = ["Search for cruises", "Help me plan a trip", "What regions do you offer?"]
        return {"text": text, "components": components, "chips": chips, "tool_calls": []}

    # --- Greeting / default branch ---
    else:
        text = "Hello! I'm your Compass cruise concierge. I can help you search for cruises, compare options, and build your perfect voyage. What would you like to explore?"
        if on_text_delta:
            on_text_delta(text)
        components = []
        chips = ["Show me Alaska cruises", "Caribbean options", "Help me compare cruises"]
        return {"text": text, "components": components, "chips": chips, "tool_calls": []}
