"""
Compass — get_itinerary tool.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Session

from ..catalog.loader import get_catalog


def get_itinerary(session: "Session", args: dict) -> dict:
    """
    Return the day-by-day itinerary for a cruise.

    Args:
        session: current session (unused for filtering, included for consistency)
        args: {"cruise_id": str}

    Returns:
        dict with keys:
          "cruise_id": str
          "days": list of day descriptors (day, port, note, tag, dot, ring, thumb)
          "day_count": int
    """
    cruise_id = args.get("cruise_id")
    if not cruise_id:
        return {"error": "missing_cruise_id", "message": "cruise_id is required"}

    catalog = get_catalog()

    # Find the cruise
    cruise = next(
        (c for c in catalog["cruises"] if c.cruise_id == cruise_id), None
    )
    if cruise is None:
        return {"error": "cruise_not_found", "message": f"Cruise {cruise_id!r} not found"}

    # Get itinerary days for this cruise
    days = [
        d for d in catalog["itineraries"] if d.cruise_id == cruise_id
    ]

    day_descriptors = [
        {
            "day": d.day,
            "port": d.port,
            "note": d.note,
            "tag": d.tag,
            "dot": d.dot,
            "ring": d.ring,
            "thumb": d.thumb,
        }
        for d in days
    ]

    return {
        "cruise_id": cruise_id,
        "days": day_descriptors,
        "day_count": len(day_descriptors),
    }
