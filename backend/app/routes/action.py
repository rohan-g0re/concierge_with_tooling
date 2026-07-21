"""
Compass — POST /action/{tool} endpoint.

One action path, multiple entry points (P6 / R21).

Every tile tap is a first-class tool call on the same TOOL_REGISTRY handlers
the model uses.  After a successful execution a compact system_event message
is appended to session.messages so the next /chat turn is state-aware.

Response shape:
  {
    "result":       <raw tool return value>,
    "components":   [<component descriptor>, ...],  # e.g. tracker_update
    "chips":        ["...", ...]                     # 2-3 contextual suggestions
  }

Error response (unknown tool, validation, tool-level error):
  {
    "error": "<code>",
    "message": "..."
  }

System events:
  Successful tool calls → {"role": "system_event", "text": "<human-readable description>"}
  Failed tool calls     → no event appended (the caller should re-try / show inline error)
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..session_store import get_or_create, update
from ..tools import TOOL_REGISTRY

router = APIRouter()


# ---------------------------------------------------------------------------
# Request body
# ---------------------------------------------------------------------------

class ActionRequest(BaseModel):
    session_id: str
    args: dict = {}


# ---------------------------------------------------------------------------
# Per-tool human-readable event descriptions
# ---------------------------------------------------------------------------

def _make_event_text(tool_name: str, args: dict, result: dict) -> str:
    """Return a compact, human-readable event string for a successful tool call."""
    if tool_name == "create_draft":
        label = result.get("label") or args.get("cruise_id", "unknown cruise")
        return f"user created a draft for {label}"

    if tool_name == "set_fare":
        pkg = args.get("package", "unknown")
        display = {"good_to_go": "Good to Go", "have_it_all": "Have It All"}.get(pkg, pkg)
        return f"user chose {display} fare package"

    if tool_name == "set_stateroom":
        cat = args.get("category", "unknown")
        loc = args.get("location")
        parts = [cat]
        if loc:
            parts.append(loc)
        return f"user selected {', '.join(parts)} stateroom"

    if tool_name == "reserve_dining":
        venue = args.get("venue_id", "unknown venue")
        night = args.get("night", "?")
        return f"user reserved {venue} night {night}"

    if tool_name == "set_land_days":
        ids = args.get("option_ids", [])
        ids_str = ", ".join(ids) if ids else "no options"
        return f"user selected land options: {ids_str}"

    if tool_name == "compare_drafts":
        ids = args.get("draft_ids", [])
        return f"user compared drafts: {', '.join(ids)}"

    if tool_name == "handoff_checkout":
        draft_id = args.get("draft_id", "unknown")
        return f"user proceeded to checkout for draft {draft_id}"

    if tool_name == "search_cruises":
        filters = {k: v for k, v in args.items() if v is not None}
        parts = [f"{k}={v}" for k, v in filters.items()]
        desc = ", ".join(parts) if parts else "all cruises"
        return f"user searched cruises: {desc}"

    if tool_name == "get_itinerary":
        cruise_id = args.get("cruise_id", "unknown")
        return f"user viewed itinerary for {cruise_id}"

    if tool_name == "list_dining":
        cruise_id = args.get("cruise_id", "unknown")
        return f"user viewed dining options for {cruise_id}"

    if tool_name == "list_land_options":
        cruise_id = args.get("cruise_id", "unknown")
        return f"user viewed land options for {cruise_id}"

    if tool_name == "set_active_draft":
        draft_id = result.get("draft_id") or args.get("draft_id", "unknown")
        label = result.get("label", draft_id)
        return f"user switched active draft to {label}"

    # Fallback
    return f"user called {tool_name}"


# ---------------------------------------------------------------------------
# Args validation
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _validate_args(tool_name: str, args: dict, schema: dict) -> dict | None:
    """
    Lightweight validation of args against the tool's JSON schema.

    Checks:
    - All required keys are present.
    - Each present key matches its declared type.

    Returns None on success, or {"error": "validation_error", "message": "..."} on failure.
    """
    params = schema.get("parameters", {})
    required = params.get("required", [])
    properties = params.get("properties", {})

    # Check required keys
    missing = [k for k in required if k not in args]
    if missing:
        return {
            "error": "validation_error",
            "message": f"Missing required args for {tool_name}: {', '.join(missing)}",
        }

    # Check types of provided keys
    for key, value in args.items():
        if key not in properties:
            continue  # Extra keys are ignored
        declared_type = properties[key].get("type")
        if declared_type is None:
            continue
        expected = _TYPE_MAP.get(declared_type)
        if expected is None:
            continue
        # bool is a subclass of int in Python; treat it strictly
        if declared_type == "integer" and isinstance(value, bool):
            return {
                "error": "validation_error",
                "message": f"Arg '{key}' must be an integer, got bool",
            }
        if not isinstance(value, expected):
            return {
                "error": "validation_error",
                "message": f"Arg '{key}' must be of type {declared_type}, got {type(value).__name__}",
            }

    return None


# ---------------------------------------------------------------------------
# Component mapping (mirrors gemini_client._map_tool_result_to_component)
# ---------------------------------------------------------------------------

def _build_components(tool_name: str, result: dict, session) -> list[dict]:
    """Build the list of component descriptors for the action response."""
    components: list[dict] = []

    if "error" in result:
        return [{"type": "error", "error": result["error"], "message": result.get("message", "")}]

    # Natural descriptor for the tool's result
    if tool_name == "search_cruises":
        cards = result.get("cruises", [])[:5]
        components.append({"type": "card_row", "cards": cards, "filters": result.get("filters", {})})

    elif tool_name == "get_itinerary":
        components.append({"type": "itinerary", **result})

    elif tool_name == "list_dining":
        components.append({"type": "dining_list", **result})

    elif tool_name == "list_land_options":
        components.append({"type": "land_options", **result})

    elif tool_name == "compare_drafts":
        components.append({"type": "comparison", **result})

    elif tool_name == "handoff_checkout":
        components.append({"type": "handoff", **result})

    # Tracker update for any tool that touches a draft
    if tool_name in ("create_draft", "set_fare", "set_stateroom", "reserve_dining", "set_land_days"):
        draft_id = result.get("draft_id") or (result.get("draft") or {}).get("draft_id")
        if draft_id:
            draft = next((d for d in session.drafts if d.draft_id == draft_id), None)
            if draft is not None:
                from ..tools.draft import checkout_entry
                from ..money import format_money
                tracker = {
                    "type": "tracker_update",
                    "draft_id": draft_id,
                    "completed_steps": list(draft.completed_steps),
                    "checkout_entry": checkout_entry(draft),
                    "total": draft.total,
                    "total_formatted": format_money(draft.total) if draft.total is not None else None,
                }
                components.append(tracker)

    # Chain next-step components for tap flow
    if tool_name == "create_draft":
        _append_fare_tiles(components, result, session)
    elif tool_name == "set_fare":
        _append_stateroom_picker(components, result, session)
    elif tool_name == "set_stateroom":
        draft_id = result.get("draft_id")
        if draft_id:
            _append_dining_tiles(components, draft_id, session)
            _append_land_builder(components, draft_id, session)
    elif tool_name == "reserve_dining":
        draft_id = result.get("draft_id")
        if draft_id:
            _append_dining_tiles(components, draft_id, session)
    elif tool_name == "set_land_days":
        draft_id = result.get("draft_id")
        if draft_id:
            _append_land_builder(components, draft_id, session)

    return components


def _fare_tiles_options() -> list[dict]:
    """Return the two standard fare option descriptors."""
    return [
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
    ]


def _append_fare_tiles(components: list, result: dict, session) -> None:
    """Append a fare_tiles descriptor after create_draft."""
    draft_id = result.get("draft_id")
    if not draft_id:
        return
    components.append({
        "type": "fare_tiles",
        "draft_id": draft_id,
        "options": _fare_tiles_options(),
    })


def _append_stateroom_picker(components: list, result: dict, session) -> None:
    """Append a stateroom_picker descriptor after set_fare."""
    draft_id = result.get("draft_id")
    if not draft_id:
        return
    draft = next((d for d in session.drafts if d.draft_id == draft_id), None)
    if draft is None:
        return
    from ..catalog.loader import get_catalog
    from ..scarcity import scarcity_for
    from ..money import format_money
    catalog = get_catalog()
    cruise_staterooms = [s for s in catalog["staterooms"] if s.cruise_id == draft.cruise_id]
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
    components.append({
        "type": "stateroom_picker",
        "draft_id": draft_id,
        "categories": categories,
        "locations": ["Forward", "Midship", "Aft"],
        "total_formatted": format_money(draft.total) if draft.total is not None else None,
        "party": session.party,
    })


def _append_dining_tiles(components: list, draft_id: str, session) -> None:
    """Append a dining_tiles descriptor for the given draft's cruise."""
    draft = next((d for d in session.drafts if d.draft_id == draft_id), None)
    if draft is None:
        return
    from ..tools.dining import list_dining
    result = list_dining(session, {"cruise_id": draft.cruise_id})
    if "error" in result:
        return
    components.append({
        "type": "dining_tiles",
        "draft_id": draft_id,
        "venues": result.get("venues", []),
    })


def _append_land_builder(components: list, draft_id: str, session) -> None:
    """Append a land_builder descriptor for the given draft's cruise (cruisetours only)."""
    draft = next((d for d in session.drafts if d.draft_id == draft_id), None)
    if draft is None:
        return
    from ..catalog.loader import get_catalog
    catalog = get_catalog()
    cruise = next((c for c in catalog["cruises"] if c.cruise_id == draft.cruise_id), None)
    if cruise is None or not cruise.is_cruisetour:
        return
    from ..tools.land import list_land_options
    result = list_land_options(session, {"cruise_id": draft.cruise_id})
    if "error" in result:
        return
    options = result.get("options", [])

    # Get currently selected option_ids from draft
    selected_ids = {ld.option_id for ld in draft.land_days}

    # Group by day
    days_map: dict = {}
    for opt in options:
        day = opt["day"]
        if day not in days_map:
            days_map[day] = []
        days_map[day].append({
            "id": opt["option_id"],
            "name": opt["name"],
            "price_formatted": opt["price_formatted"],
            "conflicts_with": opt["conflicts_with"],
            "conflict_reason": opt["conflict_reason"],
            "selected": opt["option_id"] in selected_ids,
        })

    days = [
        {"day": day, "label": f"Day {day}", "options": day_opts}
        for day, day_opts in sorted(days_map.items())
    ]

    # Build plan (selected options in day order)
    plan = []
    for day, day_opts in sorted(days_map.items()):
        for opt in day_opts:
            if opt["selected"]:
                plan.append({"day": day, "label": f"Day {day}", "option_id": opt["id"], "name": opt["name"]})

    components.append({
        "type": "land_builder",
        "draft_id": draft_id,
        "days": days,
        "plan": plan,
    })


# ---------------------------------------------------------------------------
# Contextual chips per tool
# ---------------------------------------------------------------------------

_CHIPS: dict[str, list[str]] = {
    "create_draft":      ["Choose fare package", "Select stateroom", "Reserve dining"],
    "set_fare":          ["Select stateroom", "Reserve dining", "Compare my drafts"],
    "set_stateroom":     ["Reserve dining", "Compare my drafts", "Continue to checkout"],
    "reserve_dining":    ["Add another dining night", "Compare my drafts", "Continue to checkout"],
    "set_land_days":     ["Reserve dining", "Compare my drafts", "Continue to checkout"],
    "compare_drafts":    ["Continue to checkout", "Modify a draft", "Search for more cruises"],
    "handoff_checkout":  ["Start a new search", "Help me with something else"],
    "search_cruises":    ["Tell me more about the top result", "Show Alaska cruises", "What's included?"],
    "get_itinerary":     ["Create a draft booking", "What are the dining options?", "Tell me about the ports"],
    "list_dining":       ["Reserve a dining venue", "Compare my drafts", "Continue to checkout"],
    "list_land_options": ["Select land options", "Reserve dining", "Compare my drafts"],
}

_DEFAULT_CHIPS = ["Search for cruises", "Help me plan a trip", "What regions do you offer?"]


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/action/{tool_name}")
async def action(tool_name: str, req: ActionRequest) -> dict:
    """
    Execute a TOOL_REGISTRY handler via a tile tap (or any non-chat entry point).

    Path param:  tool_name  — must be a key in TOOL_REGISTRY
    Body:        {session_id: str, args: dict}

    Returns:     {result, components, chips}  on success
                 {error, message}             on unknown tool / validation error
    Tool-level errors (sold_out, draft_cap, …) are returned as:
                 {result: {error, message}, components: [{type: error, …}], chips: […]}
    """
    # --- 1. Look up tool ---
    if tool_name not in TOOL_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "unknown_tool",
                "message": f"Tool '{tool_name}' is not registered. Available tools: {sorted(TOOL_REGISTRY.keys())}",
            },
        )

    handler, schema = TOOL_REGISTRY[tool_name]

    # --- 2. Validate args ---
    val_err = _validate_args(tool_name, req.args, schema)
    if val_err is not None:
        return val_err  # {"error": "validation_error", "message": "..."}

    # --- 3. Get/create session ---
    session = get_or_create(req.session_id)

    # --- 4. Execute handler ---
    result = handler(session, req.args)

    # --- 5. Persist session (handler may have mutated it) ---
    update(session)

    # --- 6. Append system event ---
    is_error = "error" in result
    if is_error:
        # Failed-action event — optional, document choice: we skip appending to keep
        # the history clean; the UI shows the inline error from the response.
        pass
    else:
        event_text = _make_event_text(tool_name, req.args, result)
        session.messages.append({"role": "system_event", "text": event_text})
        update(session)

    # --- 7. Build response ---
    components = _build_components(tool_name, result, session)
    chips = (_CHIPS.get(tool_name) or _DEFAULT_CHIPS)[:3]

    return {
        "result": result,
        "components": components,
        "chips": chips,
    }
