"""
Compass — Tool registry.

TOOL_REGISTRY maps tool name → (handler, json_schema_dict).
Schemas are plain JSON Schema objects usable by Gemini and the /action bridge.
"""
from __future__ import annotations

from .search import search_cruises
from .itinerary import get_itinerary
from .draft import create_draft, set_fare, set_stateroom
from .dining import list_dining, reserve_dining
from .land import list_land_options, set_land_days

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
    "list_dining": (
        list_dining,
        {
            "name": "list_dining",
            "description": "List dining venues for a cruise with per-night availability grid (available|reserved|sold_out).",
            "parameters": {
                "type": "object",
                "properties": {
                    "cruise_id": {"type": "string", "description": "The cruise identifier"},
                },
                "required": ["cruise_id"],
            },
        },
    ),
    "reserve_dining": (
        reserve_dining,
        {
            "name": "reserve_dining",
            "description": "Reserve a dining venue for a specific night on a draft. Rejects sold-out nights and double-bookings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "The draft ID"},
                    "venue_id": {"type": "string", "description": "The dining venue ID (e.g. 'saffron', 'main_dining')"},
                    "night": {"type": "integer", "description": "The cruise night number (1-indexed)"},
                },
                "required": ["draft_id", "venue_id", "night"],
            },
        },
    ),
    "list_land_options": (
        list_land_options,
        {
            "name": "list_land_options",
            "description": "List land-tour options for a cruisetour cruise. Returns error for non-cruisetour cruises.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cruise_id": {"type": "string", "description": "The cruise identifier (must be a cruisetour)"},
                },
                "required": ["cruise_id"],
            },
        },
    ),
    "set_land_days": (
        set_land_days,
        {
            "name": "set_land_days",
            "description": "Set land-day selections on a draft. Validates against catalog — rejects unknown ids, conflicting options, and same-day duplicates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "The draft ID"},
                    "option_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of land option IDs to select (e.g. ['coastal_d1', 'domed_rail_d2'])",
                    },
                },
                "required": ["draft_id", "option_ids"],
            },
        },
    ),
}
