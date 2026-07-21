"""
Compass — money formatting and draft total calculation.

Fare-price semantics
--------------------
`cruise.fare_now` is the *base "from" price*: the lowest advertised per-person
fare — Inside stateroom, no Signature Collection package, no add-ons. Marketing
cards display it as the "from" price.

The Signature Collection fare package ("have_it_all") adds
US$55 per person, per night (`FARE_PACKAGE_PER_PERSON_PER_NIGHT`) on top of the
base fare. "good_to_go" (a.k.a. "standard") adds nothing.

Design cards that show a *configured* reference price (e.g. the Denali card's
"US$ 3,828") are showing a specific configuration — Verandah + Signature
Collection — not the base "from" fare. Card display stays honest because the
"from" fare and the configured reference are distinct values.

Denali Explorer reference draft breakdown (2 guests, Signature Collection,
Verandah mid, Saffron night 9, 4 land days; 12 nights):

  Base fare (Inside, per guest)         2,682
  + Signature Collection package
    55 × 12 nights, per guest             +660
  + Verandah stateroom delta              +486
  ─────────────────────────────────────────────
  Fare per guest (configured)           3,828
  × 2 guests                            7,656

  Dining: Saffron night 9
    per guest: $38 × 2 guests             +76
  Land days: 4 × $45 per guest × 2 guests
    4 × $45 = $180 per guest × 2          +360
  ─────────────────────────────────────────────
  Add-ons total                           +436

  Grand total                           8,092  ✓
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .models import FARE_PACKAGE_PER_PERSON_PER_NIGHT

if TYPE_CHECKING:
    from .models import Draft


def format_money(amount: int) -> str:
    """Format integer dollars as 'US$ X,XXX'. e.g. format_money(3828) → 'US$ 3,828'."""
    return f"US$ {amount:,}"


def draft_total(draft: "Draft", catalog: dict) -> int:
    """
    Compute the grand total (all guests, all add-ons) for a draft.

    catalog dict keys:
      "cruises"    : list[Cruise]
      "staterooms" : list[StateroomCategory]
      "dining"     : list[DiningVenue]
      "land"       : list[LandOption]

    Raises ValueError if cruise_id not found.
    """
    from .models import Cruise, StateroomCategory, DiningVenue, LandOption

    # Resolve cruise
    cruise: Cruise | None = next(
        (c for c in catalog["cruises"] if c.cruise_id == draft.cruise_id), None
    )
    if cruise is None:
        raise ValueError(f"Cruise {draft.cruise_id!r} not found in catalog")

    # Determine party size — walk up to session if needed; default 2
    party = getattr(draft, "_party", 2)

    # Base fare (Inside stateroom, per person) — the "from" price, no package
    base_fare = cruise.fare_now

    # Signature Collection fare package delta (per person)
    # "have_it_all" adds US$55 per person per night; "good_to_go"/"standard" add 0.
    if draft.fare_package == "have_it_all":
        package_delta = FARE_PACKAGE_PER_PERSON_PER_NIGHT * cruise.nights
    else:
        package_delta = 0

    # Stateroom delta
    stateroom_delta = 0
    staterooms: list[StateroomCategory] = [
        s for s in catalog["staterooms"] if s.cruise_id == draft.cruise_id
    ]
    for cat in staterooms:
        if cat.category == draft.stateroom.category:
            stateroom_delta = cat.delta
            break

    fare_per_person = base_fare + package_delta + stateroom_delta

    # Dining add-ons
    dining_cost = 0
    venues: list[DiningVenue] = [
        v for v in catalog["dining"] if v.cruise_id == draft.cruise_id
    ]
    venue_map = {v.venue_id: v for v in venues}
    for selection in draft.dining:
        # format: "venue_id:night_N"
        parts = selection.split(":")
        venue_id = parts[0]
        if venue_id in venue_map:
            dining_cost += venue_map[venue_id].price_per_guest  # per person

    # Land add-ons
    land_cost = 0
    land_options: list[LandOption] = [
        o for o in catalog["land"] if o.cruise_id == draft.cruise_id
    ]
    land_map = {o.option_id: o for o in land_options}
    for ld in draft.land_days:
        if ld.option_id in land_map:
            land_cost += land_map[ld.option_id].price_per_guest  # per person

    cost_per_person = fare_per_person + dining_cost + land_cost
    grand_total = cost_per_person * party

    return grand_total
