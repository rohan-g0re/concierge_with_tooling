"""
Compass — Pydantic v2 data models.

Covers: Constraints, Cruise, Itinerary day, Dining venue, Land option,
Stateroom category, Draft, Session, and supporting component descriptors.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

# Signature Collection fare package: US$55 per person, per night on top of base.
FARE_PACKAGE_PER_PERSON_PER_NIGHT = 55
FarePackage = Literal["good_to_go", "have_it_all"]


# ---------------------------------------------------------------------------
# Search constraints (from user's filter bar)
# ---------------------------------------------------------------------------

class Constraints(BaseModel):
    region: Optional[str] = None          # "alaska" | "mexico" | "caribbean" | "mediterranean"
    nights_min: Optional[int] = None
    nights_max: Optional[int] = None
    embark_port: Optional[str] = None
    budget_max: Optional[int] = None      # per-person integer dollars
    party: int = 2                         # number of guests


# ---------------------------------------------------------------------------
# Cruise card (catalog row)
# ---------------------------------------------------------------------------

class Cruise(BaseModel):
    cruise_id: str
    region: str                            # "alaska" | "mexico" | "caribbean" | "mediterranean"
    name: str
    ship: str
    embark_port: str
    nights: int
    is_cruisetour: bool = False
    fare_was: int                          # per-person integer dollars
    fare_now: int                          # per-person integer dollars (base, Inside stateroom)
    popularity_score: float               # 0.0–1.0
    badge: Optional[str] = None           # e.g. "Best Value" or None
    photo: str                             # local path, e.g. "/ports/denali_range.svg"
    # Scarcity / urgency fields (present on some cruises, null on others)
    remaining_at_fare: Optional[int] = None
    historically_sells_out_weeks: Optional[int] = None
    holiday_overlap: Optional[str] = None  # e.g. "Thanksgiving week"


# ---------------------------------------------------------------------------
# Itinerary day
# ---------------------------------------------------------------------------

class ItineraryDay(BaseModel):
    cruise_id: str
    day: str                               # "Day 1", "Day 3–5", etc.
    port: str
    note: Optional[str] = None
    tag: Optional[str] = None
    dot: Optional[str] = None             # CSS color string
    ring: Optional[str] = None            # CSS color string
    thumb: bool = False                   # show thumbnail in timeline?


# ---------------------------------------------------------------------------
# Dining venue + per-night capacity
# ---------------------------------------------------------------------------

class DiningVenueNight(BaseModel):
    night: int
    capacity_remaining: int               # 0 = sold out


class DiningVenue(BaseModel):
    cruise_id: str
    venue_id: str                          # e.g. "saffron", "main_dining"
    name: str
    cuisine: list[str] = Field(default_factory=list)
    price_per_guest: int                  # additional cost per guest
    nights: list[DiningVenueNight] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Land option (cruisetours only)
# ---------------------------------------------------------------------------

class LandOption(BaseModel):
    cruise_id: str
    option_id: str                         # e.g. "coastal_d1", "domed_rail_d2"
    day: int
    name: str
    description: Optional[str] = None
    price_per_guest: int
    conflicts_with: list[str] = Field(default_factory=list)   # list of option_ids
    conflict_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Stateroom category
# ---------------------------------------------------------------------------

class StateroomCategory(BaseModel):
    cruise_id: str
    category: str                          # "Inside" | "Ocean View" | "Verandah" | "Suite"
    location: Optional[str] = None        # "Midship" | "Aft" | "Forward" | None
    delta: int                             # per-person price delta above base fare_now
    remaining_at_fare: Optional[int] = None   # None = no scarcity displayed


# ---------------------------------------------------------------------------
# Draft (PRD §7.1)
# ---------------------------------------------------------------------------

class DraftStateroom(BaseModel):
    category: str                          # "Inside" | "Ocean View" | "Verandah" | "Suite"
    location: Optional[str] = None

class DraftLandDay(BaseModel):
    day: int
    option_id: str

class Draft(BaseModel):
    draft_id: str
    cruise_id: str
    label: str                             # human-readable name for this draft
    fare_package: FarePackage              # "good_to_go" | "have_it_all" (Signature Collection)
    stateroom: DraftStateroom
    dining: list[str] = Field(default_factory=list)   # list of "{venue_id}:night_{n}" selections
    land_days: list[DraftLandDay] = Field(default_factory=list)
    completed_steps: list[int] = Field(default_factory=list)
    # Computed totals (populated by money.py)
    total_per_person: Optional[int] = None
    total: Optional[int] = None


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class Session(BaseModel):
    session_id: str
    constraints: Constraints = Field(default_factory=Constraints)
    drafts: list[Draft] = Field(default_factory=list)
    active_draft_id: Optional[str] = None
    party: int = Field(default=2, ge=1, le=4)
    messages: list[dict] = Field(default_factory=list)
