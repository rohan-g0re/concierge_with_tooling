"""
Compass — search_cruises tool.

Merges incoming constraints into session.constraints (compose), filters catalog,
ranks by popularity_score desc, returns ≤5 card descriptors.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Session

from ..catalog.loader import get_catalog
from ..money import format_money


def search_cruises(session: "Session", args: dict) -> dict:
    """
    Merge args into session constraints, filter catalog, return ≤5 cards.

    Args:
        session: current session (constraints are updated in-place)
        args: constraint fields to merge (region, nights_min, nights_max,
              embark_port, budget_max)

    Returns:
        dict with keys:
          "results": list of card descriptors (≤5)
          "filters": the active constraint set used for display
          "total_matches": int count before truncation
    """
    from ..models import Constraints

    # Merge incoming args into session constraints (compose)
    current = session.constraints
    merged = Constraints(
        region=args.get("region", current.region),
        nights_min=args.get("nights_min", current.nights_min),
        nights_max=args.get("nights_max", current.nights_max),
        embark_port=args.get("embark_port", current.embark_port),
        budget_max=args.get("budget_max", current.budget_max),
        party=current.party,
    )
    session.constraints = merged

    catalog = get_catalog()
    cruises = catalog["cruises"]

    # Filter
    results = []
    for cruise in cruises:
        if merged.region and cruise.region.lower() != merged.region.lower():
            continue
        if merged.nights_min is not None and cruise.nights < merged.nights_min:
            continue
        if merged.nights_max is not None and cruise.nights > merged.nights_max:
            continue
        if merged.embark_port:
            # substring match, case-insensitive
            if merged.embark_port.lower() not in cruise.embark_port.lower():
                continue
        if merged.budget_max is not None and cruise.fare_now > merged.budget_max:
            continue
        results.append(cruise)

    # Rank by popularity_score descending
    results.sort(key=lambda c: c.popularity_score, reverse=True)

    total_matches = len(results)
    top5 = results[:5]

    # Build card descriptors
    cards = []
    for cruise in top5:
        card = {
            "cruise_id": cruise.cruise_id,
            "name": cruise.name,
            "ship": cruise.ship,
            "region": cruise.region,
            "nights": cruise.nights,
            "embark_port": cruise.embark_port,
            "fare_was": format_money(cruise.fare_was),
            "fare_now": format_money(cruise.fare_now),
            "fare_now_raw": cruise.fare_now,
            "popularity_score": cruise.popularity_score,
            "badge": cruise.badge,
            "photo": cruise.photo,
            "remaining_at_fare": cruise.remaining_at_fare,
            "historically_sells_out_weeks": cruise.historically_sells_out_weeks,
            "holiday_overlap": cruise.holiday_overlap,
        }
        cards.append(card)

    # Active filters for display
    filters = {}
    if merged.region:
        filters["region"] = merged.region
    if merged.nights_min is not None:
        filters["nights_min"] = merged.nights_min
    if merged.nights_max is not None:
        filters["nights_max"] = merged.nights_max
    if merged.embark_port:
        filters["embark_port"] = merged.embark_port
    if merged.budget_max is not None:
        filters["budget_max"] = merged.budget_max

    return {
        "results": cards,
        "filters": filters,
        "total_matches": total_matches,
    }
