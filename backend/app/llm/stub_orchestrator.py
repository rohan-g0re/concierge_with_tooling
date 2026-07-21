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

    # --- Draft-switch branch (BEFORE search so "alaska" with a draft fires here) ---
    # Fires BEFORE the search branch so that "back to the Alaska one"
    # with an existing Alaska draft triggers a switch, not a new search.
    #
    # Gate: only attempt matching when drafts exist.
    # Incidental-mention guard: messages that describe someone else's past
    # experience ("my friend loved X", "last year", "once", "used to") without
    # explicit switch-intent verbs are passed through — no switch, no search.
    _INCIDENTAL_MARKERS = ("friend", "last year", "once", "used to", "i heard", "someone")
    _SWITCH_INTENT = ("back to", "switch", "go to", "go back", "let's look at", "the one", "my draft", "show me my", "what about my")

    _has_switch_intent = any(p in msg for p in _SWITCH_INTENT)
    _is_incidental = (
        any(m in msg for m in _INCIDENTAL_MARKERS)
        and not _has_switch_intent
    )

    if session.drafts and not is_scoped_itinerary and not _is_incidental:
        # Build a normalised representation of each draft for matching.
        # We match on: region word, cruise-name token, N-day/N-night, departure date.
        from ..catalog.loader import get_catalog as _get_catalog_sw
        _catalog_sw = _get_catalog_sw()
        _cruise_map_sw = {c.cruise_id: c for c in _catalog_sw["cruises"]}

        _REGION_WORDS = {
            "alaska": "alaska",
            "mexico": "mexico",
            "caribbean": "caribbean",
            "mediterranean": "mediterranean",
            "hawaii": "hawaii",
            "bermuda": "bermuda_bahamas",
            "bahamas": "bermuda_bahamas",
        }

        # Month abbreviations for date matching (e.g. "aug 3", "august 3")
        _MONTH_ABBREV = {
            "jan": 1, "january": 1, "feb": 2, "february": 2,
            "mar": 3, "march": 3, "apr": 4, "april": 4,
            "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
            "oct": 10, "october": 10, "nov": 11, "november": 11,
            "dec": 12, "december": 12,
        }

        def _draft_score(draft, msg_lower):
            """Return a match score for how specifically msg_lower references this draft.

            Signals are weighted so that a specific reference (duration, date,
            cruise-name) outscores a generic region-only reference:
              - region word     → 1 (weak; fires for every same-region draft)
              - cruise-name token → 2
              - duration (N-day) → 2
              - departure date   → 2

            Scores accumulate across signals. Two-pass selection in the caller
            keeps only the highest scorers: a unique top scorer with a specific
            signal switches; genuine ties (e.g. region-only for all) disambiguate.
            """
            cruise_obj = _cruise_map_sw.get(draft.cruise_id)
            score = 0

            # 1. Region word match (weak signal — same for every same-region draft)
            if cruise_obj:
                draft_region = cruise_obj.region  # e.g. "alaska"
                for word, region_key in _REGION_WORDS.items():
                    if word in msg_lower and region_key == draft_region:
                        score += 1
                        break

            # 2. Cruise name token match (any word >= 4 chars from label in msg)
            if draft.label:
                for token in draft.label.lower().split():
                    if len(token) >= 4 and token in msg_lower:
                        score += 2
                        break

            # 3. Duration match: "N-day" or "N-night" matching draft nights
            if cruise_obj:
                nights = cruise_obj.nights
                if nights:
                    patterns = [
                        f"{nights}-day", f"{nights} day",
                        f"{nights}-night", f"{nights} night",
                    ]
                    if any(p in msg_lower for p in patterns):
                        score += 2

            # 4. Departure date match: "aug 3", "august 3", "3rd august"
            if draft.departure_date:
                dep = draft.departure_date  # "YYYY-MM-DD"
                dep_month = int(dep[5:7])
                dep_day = int(dep[8:10])
                # Check "monthname day" patterns
                for abbrev, mnum in _MONTH_ABBREV.items():
                    if mnum == dep_month:
                        # "aug 3" or "aug 03"
                        if re.search(r"\b" + abbrev + r"\s+" + str(dep_day) + r"\b", msg_lower):
                            score += 2
                            break
                        # "3 aug" or "3rd aug"
                        if re.search(r"\b" + str(dep_day) + r"(?:st|nd|rd|th)?\s+" + abbrev + r"\b", msg_lower):
                            score += 2
                            break

            return score

        # Only activate draft-switch branch when switch-intent is signalled
        # OR when a region/duration/date reference clearly points to a draft
        # and it's not a search-intent ("show me", "find me", "search").
        _SEARCH_INTENT = ("show me", "find me", "search for", "find cruises", "show cruises")
        _is_search_intent = any(p in msg for p in _SEARCH_INTENT)

        # Check if any region in the message has a matching draft
        _region_in_msg = any(w in msg for w in _REGION_WORDS)

        # Two-pass scoring: score every draft, then keep only the highest scorers.
        # A unique top scorer driven by a specific signal (duration/date/name)
        # switches; a genuine tie (e.g. region-only for all same-region drafts)
        # still disambiguates.
        _scored = [(d, _draft_score(d, msg)) for d in session.drafts]
        _scored = [(d, s) for (d, s) in _scored if s > 0]

        _unique_matched = []
        if _scored:
            _top_score = max(s for (_, s) in _scored)
            _seen = set()
            for d, s in _scored:
                if s == _top_score and d.draft_id not in _seen:
                    _seen.add(d.draft_id)
                    _unique_matched.append(d)

        # Determine if draft-switch branch should fire:
        # - Must have switch-intent OR (region/duration/date match that isn't a fresh search)
        # - Must have at least one matched draft
        _should_switch = (
            _unique_matched
            and (_has_switch_intent or (not _is_search_intent and _region_in_msg))
        )

        if _should_switch:
            if len(_unique_matched) == 1:
                # Exactly one match — switch to it
                target = _unique_matched[0]
                switch_result = TOOL_REGISTRY["set_active_draft"][0](session, {"draft_id": target.draft_id})
                label = switch_result.get("label", target.draft_id)
                text = f"Switched to {label} — what would you like to explore?"
                if on_text_delta:
                    on_text_delta(text)
                components = [
                    {
                        "type": "active_draft_set",
                        "draft_id": target.draft_id,
                        "label": label,
                    }
                ]
                chips = ["Tell me about dining", "Choose stateroom", "Compare my drafts"]
                return {"text": text, "components": components, "chips": chips, "tool_calls": ["set_active_draft"]}

            else:
                # 2+ matches — disambiguate
                matched_ids = [d.draft_id for d in _unique_matched]
                disambig_result = TOOL_REGISTRY["disambiguate_drafts"][0](session, {"draft_ids": matched_ids})
                text = "Which one do you mean?"
                if on_text_delta:
                    on_text_delta(text)
                components = [
                    {
                        "type": "draft_disambiguation",
                        "candidates": disambig_result.get("candidates", []),
                        "active_draft_id": disambig_result.get("active_draft_id"),
                    }
                ]
                chips = ["Pick the first option", "Show me all my drafts", "Start a new search"]
                return {"text": text, "components": components, "chips": chips, "tool_calls": ["disambiguate_drafts"]}

        # If region referenced but NO matching draft → fall through to search branch below.
        # (no explicit else needed — execution continues)

    # --- Cruise search branch ---
    # Incidental mentions ("my friend loved the Caribbean last year") must not
    # trigger a fresh search either — they fall through to the default reply.
    if not is_scoped_itinerary and not _is_incidental and any(
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
        range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)[\s-]*day", msg)
        single_match = re.search(r"(\d+)[\s-]*day", msg)
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

        no_exact = result.get("no_exact", False)
        if no_exact:
            preamble_1 = "No exact matches — here are the closest options."
            preamble_2 = ""
        else:
            preamble_1 = "I found some great options for you."
            preamble_2 = " Here's what matches your request:"
        if on_text_delta:
            on_text_delta(preamble_1)
            if preamble_2:
                on_text_delta(preamble_2)
        text = preamble_1 + preamble_2

        card_row: dict = {
            "type": "card_row",
            "cards": result.get("results", [])[:5],
            "filters": result.get("filters", {}),
        }
        # Forward sections/no_exact when present (Unit 4)
        if "sections" in result:
            sections = result["sections"]
            capped_sections = [
                {"label": s["label"], "cards": s["cards"][:5]}
                for s in sections
            ]
            card_row["sections"] = capped_sections
            card_row["no_exact"] = no_exact

        components = [
            card_row,
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
