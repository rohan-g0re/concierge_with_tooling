"""
Compass — Tool registry.

TOOL_REGISTRY maps tool name → (handler, json_schema_dict).
Schemas are plain JSON Schema objects usable by Gemini and the /action bridge.
"""
from __future__ import annotations

from .search import search_cruises
from .itinerary import get_itinerary
from .draft import create_draft, set_fare, set_stateroom

TOOL_REGISTRY: dict[str, tuple] = {
    "search_cruises": (
        search_cruises,
        {
            "name": "search_cruises",
            "description": "Search and filter cruises by constraints. Constraints compose — each call merges into session constraints.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region": {"type": "string", "description": "Cruise region: alaska|mexico|caribbean|mediterranean"},
                    "nights_min": {"type": "integer", "description": "Minimum number of nights"},
                    "nights_max": {"type": "integer", "description": "Maximum number of nights"},
                    "embark_port": {"type": "string", "description": "Embarkation port (substring match)"},
                    "budget_max": {"type": "integer", "description": "Maximum per-person budget in USD"},
                },
                "required": [],
            },
        },
    ),
    "get_itinerary": (
        get_itinerary,
        {
            "name": "get_itinerary",
            "description": "Get the day-by-day itinerary for a cruise.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cruise_id": {"type": "string", "description": "The cruise identifier"},
                },
                "required": ["cruise_id"],
            },
        },
    ),
    "create_draft": (
        create_draft,
        {
            "name": "create_draft",
            "description": "Create a new booking draft for a cruise. Max 3 drafts per session.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cruise_id": {"type": "string", "description": "The cruise to book"},
                },
                "required": ["cruise_id"],
            },
        },
    ),
    "set_fare": (
        set_fare,
        {
            "name": "set_fare",
            "description": "Set the fare package for a draft.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "The draft ID"},
                    "package": {"type": "string", "description": "Fare package: good_to_go|have_it_all"},
                },
                "required": ["draft_id", "package"],
            },
        },
    ),
    "set_stateroom": (
        set_stateroom,
        {
            "name": "set_stateroom",
            "description": "Set the stateroom category and location for a draft.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "The draft ID"},
                    "category": {"type": "string", "description": "Stateroom category: Inside|Ocean View|Verandah|Suite"},
                    "location": {"type": "string", "description": "Stateroom location: Midship|Aft|Forward"},
                },
                "required": ["draft_id", "category"],
            },
        },
    ),
}
