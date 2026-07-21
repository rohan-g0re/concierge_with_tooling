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

    # A scoped itinerary message looks like:
    #   "About the <name> itinerary (<cruise_id>): <question>"
    # These frequently contain the word "cruise"/"cruisetour" in the cruise
    # name, so they must be detected BEFORE the search branch or search would
    # hijack the turn. Route scoped/itinerary messages to the itinerary Q&A path.
    is_scoped_itinerary = bool(re.search(r"\(([a-z][a-z0-9_]+)\):", msg)) or "itinerary" in msg

    # --- Cruise search branch ---
    if not is_scoped_itinerary and any(
        kw in msg for kw in ("alaska", "mexico", "caribbean", "mediterranean", "hawaii", "bermuda", "bahamas", "cruise", "sail", "voyage", "october", "november", "december", "january", "february", "march", "april", "august", "september", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec", "return before", "back before", "returning before", "return by", "back by")
    ):
        args: dict = {}

        # region
        if "hawaii" in msg:
            args["region"] = "hawaii"
        elif "bermuda" in msg or "bahamas" in msg:
            args["region"] = "bermuda_bahamas"
        elif "alaska" in msg:
            args["region"] = "alaska"
        elif "mexico" in msg:
            args["region"] = "mexico"
        elif "caribbean" in msg:
            args["region"] = "caribbean"
        elif "mediterranean" in msg:
            args["region"] = "mediterranean"

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

        # return_by: "return(ing) before/by <date>", "back before/by <date>"
        # Parse BEFORE month scan so the matched date span can be excised,
        # preventing a month abbreviation inside the return_by clause (e.g.
        # "back before dec 28") from being mistaken for a month filter.
        return_by_match = re.search(
            r"(?:return(?:ing)?\s+(?:before|by)|back\s+(?:before|by))\s+([a-z]+\s+\d{1,2}|\d{4}-\d{2}-\d{2})",
            msg,
        )
        if return_by_match:
            args["return_by"] = return_by_match.group(1)

        # Build a version of msg with the return_by span removed so month
        # abbreviations that appear only inside that clause are not picked up.
        msg_for_month = (
            msg[: return_by_match.start()] + msg[return_by_match.end():]
            if return_by_match
            else msg
        )

        # month: parse month names (full + 3-letter abbrevs, case-insensitive)
        _MONTH_MAP = {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9, "sept": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12,
        }
        for month_name, month_int in _MONTH_MAP.items():
            if re.search(r"\b" + month_name + r"\b", msg_for_month):
                args["month"] = month_int
                break

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
    elif is_scoped_itinerary or any(kw in msg for kw in ("itinerary", "ports", "days at sea", "before ", "day ")):
        # Extract cruise_id from scoped message format: "About the <name> itinerary (<cruise_id>): ..."
        scoped_match = re.search(r"\(([a-z][a-z0-9_]+)\):", msg)
        cruise_id_match = re.search(r"\b[a-z]{2}-\d{3}\b", msg)
        if scoped_match:
            cruise_id = scoped_match.group(1)
        elif cruise_id_match:
            cruise_id = cruise_id_match.group(0)
        elif session.constraints and hasattr(session.constraints, "__iter__"):
            # try to get first cruise from constraints
            try:
                cruise_id = session.constraints[0] if session.constraints else "denali_explorer"
            except (TypeError, IndexError):
                cruise_id = "denali_explorer"
        else:
            cruise_id = "denali_explorer"

        result = TOOL_REGISTRY["get_itinerary"][0](session, {"cruise_id": cruise_id})
        days = result.get("days", [])

        # --- Scoped Q&A: "before <port>" → list ports with lower day numbers ---
        before_match = re.search(r"\bbefore\s+([a-z][\w\s]+)", msg)
        if before_match and days:
            target_port = before_match.group(1).strip().rstrip("?!.")
            # Find the first day whose port contains the target (case-insensitive)
            target_day_idx = None
            for i, d in enumerate(days):
                if target_port.lower() in d["port"].lower():
                    target_day_idx = i
                    break

            if target_day_idx is not None and target_day_idx > 0:
                earlier = days[:target_day_idx]
                port_list = "; ".join(f"{d['day']}: {d['port']}" for d in earlier)
                text = (
                    f"Before {days[target_day_idx]['port']} ({days[target_day_idx]['day']}), "
                    f"the itinerary visits: {port_list}."
                )
            elif target_day_idx == 0:
                text = f"{days[0]['port']} is the first port — nothing comes before it."
            else:
                text = (
                    f"I couldn't find '{target_port}' in this itinerary. "
                    f"Ports visited: "
                    + "; ".join(f"{d['day']}: {d['port']}" for d in days)
                    + "."
                )
            if on_text_delta:
                on_text_delta(text)
            chips = ["Tell me about the ports", "Create a draft booking", "What are the dining options?"]
            return {
                "text": text,
                "components": [{"type": "itinerary", **result}],
                "chips": chips,
                "tool_calls": ["get_itinerary"],
            }

        # Generic itinerary display
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

    # --- Fare tiles branch ---
    elif any(kw in msg for kw in ("fare", "package", "signature")):
        components = [
            {
                "type": "fare_tiles",
                "draft_id": session.active_draft_id,
                "options": [
                    {
                        "id": "good_to_go",
                        "name": "Standard Fare",
                        "label": "Included in your fare",
                        "amenities": [
                            {"text": "Stateroom & main dining", "included": True},
                            {"text": "Entertainment & enrichment", "included": True},
                            {"text": "Beverages, specialty dining, Wi-Fi billed separately", "included": False},
                        ],
                        "cta": "Keep Standard",
                        "deposit_note": "Deposit US$ 350 per guest, refundable for 30 days.",
                    },
                    {
                        "id": "have_it_all",
                        "name": "The Signature Collection",
                        "badge": "Recommended",
                        "delta_per_day": "+US$ 55 /pp/day",
                        "amenities": [
                            {"text": "Signature Beverage Package", "included": True},
                            {"text": "One Specialty Dining night", "included": True},
                            {"text": "US$ 100 Shore Excursion credit", "included": True},
                            {"text": "Wi-Fi throughout the voyage", "included": True},
                        ],
                        "cta": "Selected",
                        "sharing_note": "Guests in the same stateroom share one package selection.",
                    },
                ],
            }
        ]
        chips = ["Choose stateroom", "Tell me more", "Compare my drafts"]
        text = "Here are the available fare packages for your cruise."
        if on_text_delta:
            on_text_delta(text)
        return {"text": text, "components": components, "chips": chips, "tool_calls": []}

    # --- Stateroom picker branch ---
    elif any(kw in msg for kw in ("stateroom", "room", "cabin")):
        from ..catalog.loader import get_catalog
        from ..scarcity import scarcity_for
        from ..money import format_money

        catalog = get_catalog()

        # Get active draft to know the cruise
        draft = None
        if session.active_draft_id:
            draft = next((d for d in session.drafts if d.draft_id == session.active_draft_id), None)

        cruise_id = draft.cruise_id if draft else None

        # Get stateroom categories for this cruise (or defaults)
        if cruise_id:
            cruise_staterooms = [s for s in catalog["staterooms"] if s.cruise_id == cruise_id]
        else:
            cruise_staterooms = []

        # Build categories list with scarcity signals
        categories = []
        for s in cruise_staterooms:
            scarcity_signals = scarcity_for(s)
            cat = {
                "category": s.category,
                "delta": s.delta,
                "delta_formatted": f"+US$ {s.delta:,}" if s.delta > 0 else "Included",
                "remaining_at_fare": s.remaining_at_fare,
            }
            if scarcity_signals:
                cat["scarcity"] = scarcity_signals
            categories.append(cat)

        # Compute total_formatted from draft if available
        total_formatted = None
        if draft and draft.total is not None:
            total_formatted = format_money(draft.total)

        components = [
            {
                "type": "stateroom_picker",
                "draft_id": session.active_draft_id,
                "categories": categories,
                "locations": ["Forward", "Midship", "Aft"],
                "total_formatted": total_formatted,
            }
        ]
        chips = ["Choose Verandah", "Tell me about staterooms", "Compare my drafts"]
        text = "Choose your stateroom category and preferred location."
        if on_text_delta:
            on_text_delta(text)
        return {"text": text, "components": components, "chips": chips, "tool_calls": []}

    # --- Dining branch ---
    elif "dining" in msg or "restaurant" in msg or "dinner" in msg:
        draft = None
        if session.active_draft_id:
            draft = next((d for d in session.drafts if d.draft_id == session.active_draft_id), None)
        if draft is None and session.drafts:
            draft = session.drafts[0]

        if draft:
            from ..tools.dining import list_dining
            result = list_dining(session, {"cruise_id": draft.cruise_id})
            if "error" not in result:
                text = "Here are the dining venues for your cruise."
                if on_text_delta:
                    on_text_delta(text)
                components = [{
                    "type": "dining_tiles",
                    "draft_id": draft.draft_id,
                    "venues": result.get("venues", []),
                }]
                chips = ["Reserve a dining night", "Compare my drafts", "Continue to checkout"]
                return {"text": text, "components": components, "chips": chips, "tool_calls": ["list_dining"]}

        text = "Create a draft first to see dining options."
        if on_text_delta:
            on_text_delta(text)
        return {"text": text, "components": [], "chips": ["Search for cruises"], "tool_calls": []}

    # --- Land/excursion branch ---
    elif "land option" in msg or "excursion" in msg or ("land" in msg and ("tour" in msg or "option" in msg)):
        draft = None
        if session.active_draft_id:
            draft = next((d for d in session.drafts if d.draft_id == session.active_draft_id), None)
        if draft is None and session.drafts:
            draft = session.drafts[0]

        if draft:
            from ..catalog.loader import get_catalog
            catalog = get_catalog()
            cruise = next((c for c in catalog["cruises"] if c.cruise_id == draft.cruise_id), None)
            if cruise and cruise.is_cruisetour:
                from ..tools.land import list_land_options
                result = list_land_options(session, {"cruise_id": draft.cruise_id})
                if "error" not in result:
                    from ..routes.action import _append_land_builder
                    components: list = []
                    _append_land_builder(components, draft.draft_id, session)
                    text = "Here are the land tour options for your cruisetour."
                    if on_text_delta:
                        on_text_delta(text)
                    chips = ["Select land options", "Reserve dining", "Compare my drafts"]
                    return {"text": text, "components": components, "chips": chips, "tool_calls": ["list_land_options"]}

        text = "Land options are only available for cruisetour itineraries. Create a cruisetour draft to see land options."
        if on_text_delta:
            on_text_delta(text)
        return {"text": text, "components": [], "chips": ["Search for cruises"], "tool_calls": []}

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
