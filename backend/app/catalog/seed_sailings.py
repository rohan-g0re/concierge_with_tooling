"""
Compass — Catalog seeder: adds sailing series to every cruise and expands
the catalog from 4 regions to 6 (hawaii, bermuda_bahamas).

Usage (from backend/):
    python -m app.catalog.seed_sailings

Note: the server caches catalog data at boot — a server restart is required
after reseeding for the new data to take effect.

Determinism guarantee: running this script multiple times produces byte-identical
cruises.json output. No random is used; all data is derived from fixed inputs.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

DEMO_ANCHOR = date(2026, 7, 1)

# Departure interval in days between consecutive sailings, by region
CADENCE_DAYS: dict[str, int] = {
    "alaska": 7,
    "mexico": 7,
    "caribbean": 7,
    "mediterranean": 14,
    "hawaii": 14,
    "bermuda_bahamas": 7,
}

_DATA_DIR = Path(__file__).parent / "data"

# ---------------------------------------------------------------------------
# New cruise records (added if absent by cruise_id)
# ---------------------------------------------------------------------------

NEW_CRUISES: list[dict] = [
    {
        "cruise_id": "hawaii_nonstop",
        "region": "hawaii",
        "name": "Hawaii Nonstop — Round Voyage",
        "ship": "ms Pacific Star",
        "embark_port": "Los Angeles, California",
        "nights": 15,
        "is_cruisetour": False,
        "fare_was": 3499,
        "fare_now": 2899,
        "popularity_score": 0.82,
        "badge": None,
        "photo": "/ports/inside_passage.svg",
        "remaining_at_fare": None,
        "historically_sells_out_weeks": None,
        "holiday_overlap": None,
    },
    {
        "cruise_id": "hawaii_neighbor_islands",
        "region": "hawaii",
        "name": "Neighbor Islands Explorer",
        "ship": "ms Aloha Spirit",
        "embark_port": "Honolulu, Hawaii",
        "nights": 10,
        "is_cruisetour": False,
        "fare_was": 2799,
        "fare_now": 2299,
        "popularity_score": 0.79,
        "badge": None,
        "photo": "/ports/glacier_bay.svg",
        "remaining_at_fare": 8,
        "historically_sells_out_weeks": 5,
        "holiday_overlap": None,
    },
    {
        "cruise_id": "hawaii_maui_big_island",
        "region": "hawaii",
        "name": "Maui & Big Island Discovery",
        "ship": "ms Pacific Star",
        "embark_port": "Honolulu, Hawaii",
        "nights": 12,
        "is_cruisetour": False,
        "fare_was": 3199,
        "fare_now": 2599,
        "popularity_score": 0.75,
        "badge": "Best Value",
        "photo": "/ports/cabo.svg",
        "remaining_at_fare": None,
        "historically_sells_out_weeks": None,
        "holiday_overlap": None,
    },
    {
        "cruise_id": "bermuda_classic",
        "region": "bermuda_bahamas",
        "name": "Classic Bermuda Getaway",
        "ship": "ms Atlantic Star",
        "embark_port": "New York, New York",
        "nights": 7,
        "is_cruisetour": False,
        "fare_was": 1699,
        "fare_now": 1349,
        "popularity_score": 0.84,
        "badge": None,
        "photo": "/ports/nassau.svg",
        "remaining_at_fare": 6,
        "historically_sells_out_weeks": 4,
        "holiday_overlap": None,
    },
    {
        "cruise_id": "bermuda_pink_sand",
        "region": "bermuda_bahamas",
        "name": "Pink Sand & Turquoise Water",
        "ship": "ms Atlantic Star",
        "embark_port": "Baltimore, Maryland",
        "nights": 7,
        "is_cruisetour": False,
        "fare_was": 1599,
        "fare_now": 1299,
        "popularity_score": 0.78,
        "badge": None,
        "photo": "/ports/st_thomas.svg",
        "remaining_at_fare": None,
        "historically_sells_out_weeks": None,
        "holiday_overlap": None,
    },
    {
        "cruise_id": "bahamas_weekend",
        "region": "bermuda_bahamas",
        "name": "Bahamas Weekend Escape",
        "ship": "ms Paradise Cay",
        "embark_port": "New York, New York",
        "nights": 5,
        "is_cruisetour": False,
        "fare_was": 999,
        "fare_now": 799,
        "popularity_score": 0.72,
        "badge": "Best Value",
        "photo": "/ports/nassau.svg",
        "remaining_at_fare": None,
        "historically_sells_out_weeks": None,
        "holiday_overlap": None,
    },
    {
        "cruise_id": "bahamas_grand_escape",
        "region": "bermuda_bahamas",
        "name": "Grand Bahama Island Escape",
        "ship": "ms Paradise Cay",
        "embark_port": "Baltimore, Maryland",
        "nights": 6,
        "is_cruisetour": False,
        "fare_was": 1199,
        "fare_now": 949,
        "popularity_score": 0.69,
        "badge": None,
        "photo": "/ports/barbados.svg",
        "remaining_at_fare": 12,
        "historically_sells_out_weeks": None,
        "holiday_overlap": None,
    },
]

# Minimal itinerary day 2 ports for new cruises (deterministic lookup)
_NEW_CRUISE_MID_PORTS: dict[str, str] = {
    "hawaii_nonstop": "Maui, Hawaii",
    "hawaii_neighbor_islands": "Maui, Hawaii",
    "hawaii_maui_big_island": "Hilo, Hawaii (Big Island)",
    "bermuda_classic": "Hamilton, Bermuda",
    "bermuda_pink_sand": "Hamilton, Bermuda",
    "bahamas_weekend": "Nassau, Bahamas",
    "bahamas_grand_escape": "Freeport, Grand Bahama",
}


# ---------------------------------------------------------------------------
# Sailing generator
# ---------------------------------------------------------------------------

def _generate_sailings(cruise_id: str, region: str, nights: int) -> list[dict]:
    """
    Generate sailing series for a cruise deterministically.

    Returns list of dicts with keys: sailing_id, departure_date, return_date.
    """
    cadence = CADENCE_DAYS.get(region, 7)
    horizon = DEMO_ANCHOR + timedelta(days=183)  # ~6 months
    max_sailings = 16
    min_sailings = 8

    sailings: list[dict] = []
    dep = DEMO_ANCHOR

    while len(sailings) < max_sailings:
        ret = dep + timedelta(days=nights)
        dep_str = dep.isoformat()
        ret_str = ret.isoformat()
        sailings.append(
            {
                "sailing_id": f"{cruise_id}-{dep_str}",
                "departure_date": dep_str,
                "return_date": ret_str,
            }
        )
        dep = dep + timedelta(days=cadence)
        # Stop if we've hit min and gone past the horizon
        if len(sailings) >= min_sailings and dep > horizon:
            break

    return sailings


# ---------------------------------------------------------------------------
# Satellite helpers
# ---------------------------------------------------------------------------

def _stateroom_rows(cruise_id: str) -> list[dict]:
    return [
        {"cruise_id": cruise_id, "category": "Inside", "location": None, "delta": 0, "remaining_at_fare": None},
        {"cruise_id": cruise_id, "category": "Ocean View", "location": None, "delta": 214, "remaining_at_fare": None},
        {"cruise_id": cruise_id, "category": "Verandah", "location": "Midship", "delta": 486, "remaining_at_fare": None},
        {"cruise_id": cruise_id, "category": "Suite", "location": None, "delta": 1240, "remaining_at_fare": None},
    ]


def _dining_rows(cruise_id: str, nights: int) -> list[dict]:
    main_nights = [{"night": n, "capacity_remaining": 15 + (n % 16)} for n in range(1, nights + 1)]
    lido_nights = [{"night": n, "capacity_remaining": 50} for n in range(1, nights + 1)]
    return [
        {
            "cruise_id": cruise_id,
            "venue_id": "main_dining",
            "name": "Main Dining Room",
            "cuisine": ["American", "Continental"],
            "price_per_guest": 0,
            "nights": main_nights,
        },
        {
            "cruise_id": cruise_id,
            "venue_id": "lido",
            "name": "Lido Buffet",
            "cuisine": ["Casual", "Buffet"],
            "price_per_guest": 0,
            "nights": lido_nights,
        },
    ]


def _itinerary_rows(cruise_id: str, embark_port: str) -> list[dict]:
    mid_port = _NEW_CRUISE_MID_PORTS.get(cruise_id, "At Sea")
    return [
        {
            "cruise_id": cruise_id,
            "day": "Day 1",
            "port": embark_port,
            "note": "Embark · departs 4:00 PM",
            "tag": None,
            "dot": "#C8A45C",
            "ring": "#C8A45C",
            "thumb": True,
        },
        {
            "cruise_id": cruise_id,
            "day": "Day 3",
            "port": mid_port,
            "note": None,
            "tag": None,
            "dot": "#0C2340",
            "ring": "#0C2340",
            "thumb": True,
        },
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> list:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: list) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def seed() -> None:
    """Seed sailings into cruises.json and add new region cruises + satellite data."""
    cruises_path = _DATA_DIR / "cruises.json"
    staterooms_path = _DATA_DIR / "staterooms.json"
    dining_path = _DATA_DIR / "dining.json"
    itineraries_path = _DATA_DIR / "itineraries.json"
    land_options_path = _DATA_DIR / "land_options.json"

    cruises: list[dict] = _load_json(cruises_path)
    staterooms: list[dict] = _load_json(staterooms_path)
    dining: list[dict] = _load_json(dining_path)
    itineraries: list[dict] = _load_json(itineraries_path)
    land_options: list[dict] = _load_json(land_options_path)

    # Existing cruise IDs
    existing_ids = {c["cruise_id"] for c in cruises}

    # Add new cruises if absent
    for new_cruise in NEW_CRUISES:
        if new_cruise["cruise_id"] not in existing_ids:
            cruises.append(new_cruise)
            cid = new_cruise["cruise_id"]
            nights = new_cruise["nights"]
            embark = new_cruise["embark_port"]

            staterooms.extend(_stateroom_rows(cid))
            dining.extend(_dining_rows(cid, nights))
            itineraries.extend(_itinerary_rows(cid, embark))
            # land_options: no additions (not cruisetours)

    # Generate sailings for every cruise
    for cruise in cruises:
        cid = cruise["cruise_id"]
        region = cruise["region"]
        nights = cruise["nights"]
        cruise["sailings"] = _generate_sailings(cid, region, nights)

    # Write all files
    _write_json(cruises_path, cruises)
    _write_json(staterooms_path, staterooms)
    _write_json(dining_path, dining)
    _write_json(itineraries_path, itineraries)
    _write_json(land_options_path, land_options)

    total = len(cruises)
    print(f"Seeded {total} cruises with sailings.")
    regions = {c["region"] for c in cruises}
    print(f"Regions: {sorted(regions)}")
    for c in cruises:
        print(f"  {c['cruise_id']}: {len(c['sailings'])} sailings")


if __name__ == "__main__":
    seed()
