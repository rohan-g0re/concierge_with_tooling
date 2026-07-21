"""
Compass — search_cruises tool.

Merges incoming constraints into session.constraints (compose), filters catalog,
ranks by popularity_score desc, returns ≤5 card descriptors.

Date filtering (Unit 3):
  month     — departure month 1-12; selects earliest sailing in that month ≥ anchor
  return_by — latest acceptable return date (ISO or natural "Dec 28" style);
               selects latest sailing whose return_date ≤ return_by
  Cruises with no satisfying sailing are excluded.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Session

from ..catalog.loader import get_catalog
from ..money import format_money

# Demo anchor — sailings are generated relative to this date
DEMO_ANCHOR = date(2026, 7, 1)

# Month name → int lookup (full names + 3-letter abbreviations, lower-case)
_MONTH_ABBREVS: dict[str, int] = {
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


def _parse_return_by(value: str) -> date | None:
    """
    Parse a return_by string into a date.

    Accepts:
      - ISO YYYY-MM-DD  (e.g. "2026-12-28")
      - "<Month> <day>" (e.g. "Dec 28", "December 28")

    Year inference: the resolved date must be ≥ DEMO_ANCHOR. If the bare
    month/day resolves to a date before the anchor, add one year.

    Returns None on any parse failure (caller ignores malformed input).
    """
    value = value.strip()

    # ISO format
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    # Try "Month Day" variants: "Dec 28", "December 28", "dec 28"
    m = re.fullmatch(
        r"([A-Za-z]+)\s+(\d{1,2})",
        value,
    )
    if m:
        month_name = m.group(1).lower()
        day = int(m.group(2))
        month_num = _MONTH_ABBREVS.get(month_name)
        if month_num is None:
            return None
        year = DEMO_ANCHOR.year
        try:
            d = date(year, month_num, day)
        except ValueError:
            return None
        if d < DEMO_ANCHOR:
            try:
                d = date(year + 1, month_num, day)
            except ValueError:
                return None
        return d

    return None


def _select_sailing(cruise, *, month: int | None, return_by: date | None):
    """
    Select the context-matched sailing from cruise.sailings.

    Rules:
      - month set only: earliest sailing where departure_date month == month,
        departure_date >= DEMO_ANCHOR.
      - return_by set only: latest sailing where return_date <= return_by.
      - both set: sailings satisfying both constraints, pick earliest departure.
      - neither: earliest sailing with departure_date >= DEMO_ANCHOR.

    Returns the matching sailing dict, or None if no sailing qualifies.
    """
    sailings = cruise.sailings  # list[Sailing]
    if not sailings:
        return None

    candidates = []

    if month is None and return_by is None:
        # Next upcoming departure >= anchor
        for s in sailings:
            dep = date.fromisoformat(s.departure_date)
            if dep >= DEMO_ANCHOR:
                candidates.append(s)
        if not candidates:
            return None
        return min(candidates, key=lambda s: s.departure_date)

    if month is not None and return_by is None:
        for s in sailings:
            dep = date.fromisoformat(s.departure_date)
            if dep >= DEMO_ANCHOR and dep.month == month:
                candidates.append(s)
        if not candidates:
            return None
        return min(candidates, key=lambda s: s.departure_date)

    if month is None and return_by is not None:
        for s in sailings:
            ret = date.fromisoformat(s.return_date)
            if ret <= return_by:
                candidates.append(s)
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.return_date)

    # Both month and return_by set
    for s in sailings:
        dep = date.fromisoformat(s.departure_date)
        ret = date.fromisoformat(s.return_date)
        if dep >= DEMO_ANCHOR and dep.month == month and ret <= return_by:
            candidates.append(s)
    if not candidates:
        return None
    return min(candidates, key=lambda s: s.departure_date)


def _alt_sailings(cruise, selected_sailing, *, month: int | None, return_by: date | None) -> list[dict]:
    """
    Return up to 4 alternate sailings (other than selected_sailing) that
    satisfy the same constraints, or nearest sailings if fewer than 4 qualify.
    """
    selected_id = selected_sailing.sailing_id if selected_sailing else None
    sailings = cruise.sailings

    # Sailings satisfying the constraint
    qualifying = []
    for s in sailings:
        if s.sailing_id == selected_id:
            continue
        dep = date.fromisoformat(s.departure_date)
        ret = date.fromisoformat(s.return_date)
        ok = dep >= DEMO_ANCHOR
        if month is not None and dep.month != month:
            ok = False
        if return_by is not None and ret > return_by:
            ok = False
        if ok:
            qualifying.append(s)

    qualifying.sort(key=lambda s: s.departure_date)
    alts = qualifying[:4]

    # If fewer than 4, pad with nearest sailings (regardless of constraint)
    if len(alts) < 4:
        extras = [s for s in sailings if s.sailing_id != selected_id and s not in alts]
        extras.sort(key=lambda s: abs(
            (date.fromisoformat(s.departure_date) - date.fromisoformat(selected_sailing.departure_date)).days
            if selected_sailing else 0
        ))
        alts = (alts + extras)[: 4]

    return [
        {
            "sailing_id": s.sailing_id,
            "departure_date": s.departure_date,
            "return_date": s.return_date,
        }
        for s in alts
    ]


def _build_near_miss_card(cruise, sailing) -> dict:
    """Build a card descriptor for a near-miss cruise+sailing pair."""
    return {
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
        "sailing_id": sailing.sailing_id,
        "departure_date": sailing.departure_date,
        "return_date": sailing.return_date,
        "alt_sailings": [],
    }


def search_cruises(session: "Session", args: dict) -> dict:
    """
    Merge args into session constraints, filter catalog, return ≤5 cards.

    Args:
        session: current session (constraints are updated in-place)
        args: constraint fields to merge (region, nights_min, nights_max,
              embark_port, budget_max, month, return_by)

    Returns:
        dict with keys:
          "results": list of card descriptors (≤5)
          "filters": the active constraint set used for display
          "total_matches": int count before truncation
    """
    from ..models import Constraints

    # Merge incoming args into session constraints (compose)
    current = session.constraints

    # Parse return_by — normalise and ignore malformed values
    raw_return_by = args.get("return_by", current.return_by)
    return_by_date: date | None = None
    return_by_str: str | None = None
    if raw_return_by is not None:
        parsed = _parse_return_by(raw_return_by)
        if parsed is not None:
            return_by_date = parsed
            return_by_str = parsed.isoformat()
        # else: malformed — leave both None

    month_val = args.get("month", current.month)

    merged = Constraints(
        region=args.get("region", current.region),
        nights_min=args.get("nights_min", current.nights_min),
        nights_max=args.get("nights_max", current.nights_max),
        embark_port=args.get("embark_port", current.embark_port),
        budget_max=args.get("budget_max", current.budget_max),
        party=current.party,
        month=month_val,
        return_by=return_by_str,
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

        # Date filtering — select context-matched sailing
        sailing = _select_sailing(
            cruise,
            month=merged.month,
            return_by=return_by_date,
        )
        if sailing is None:
            # No satisfying sailing → exclude cruise
            continue

        results.append((cruise, sailing))

    # Rank by popularity_score descending
    results.sort(key=lambda t: t[0].popularity_score, reverse=True)

    total_matches = len(results)
    top5 = results[:5]

    # Build card descriptors
    cards = []
    for cruise, sailing in top5:
        alts = _alt_sailings(
            cruise,
            sailing,
            month=merged.month,
            return_by=return_by_date,
        )
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
            # Date fields (Unit 3)
            "sailing_id": sailing.sailing_id,
            "departure_date": sailing.departure_date,
            "return_date": sailing.return_date,
            "alt_sailings": alts,
        }
        cards.append(card)

    # Active filters for display
    filters: dict = {}
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
    if merged.month is not None:
        filters["month"] = merged.month
    if merged.return_by is not None:
        filters["return_by"] = merged.return_by

    # -----------------------------------------------------------------------
    # Sections — near-miss logic (Unit 4)
    # Only when a date/duration constraint is active.
    # -----------------------------------------------------------------------
    has_date_or_duration = (
        merged.nights_min is not None
        or merged.nights_max is not None
        or merged.month is not None
        or merged.return_by is not None
    )

    if not has_date_or_duration:
        return {
            "results": cards,
            "filters": filters,
            "total_matches": total_matches,
        }

    # Exact-match section (same as `cards`)
    no_exact = len(cards) == 0
    sections: list[dict] = [{"label": None, "cards": cards}]

    # Track which cruise_ids are already shown (in exact section)
    shown_ids: set[str] = {c["cruise_id"] for c in cards}

    # All cruises (not already in exact) that pass region/port/budget filters
    # (we relax the nights/date constraints for near-miss)
    def _passes_non_date_filters(cruise) -> bool:
        if merged.region and cruise.region.lower() != merged.region.lower():
            return False
        if merged.embark_port and merged.embark_port.lower() not in cruise.embark_port.lower():
            return False
        if merged.budget_max is not None and cruise.fare_now > merged.budget_max:
            return False
        return True

    def _select_sailing_relaxed_date(cruise, *, allow_any_month: bool, allow_any_date: bool):
        """Select a sailing with relaxed date constraints."""
        month_to_use = None if allow_any_month else merged.month
        return_by_to_use = None if allow_any_date else return_by_date
        return _select_sailing(cruise, month=month_to_use, return_by=return_by_to_use)

    # ---- Section 1: Duration ± (if nights band set) ----
    if merged.nights_min is not None or merged.nights_max is not None:
        # Determine the reference N for label text
        if merged.nights_min == merged.nights_max and merged.nights_min is not None:
            ref_n = merged.nights_min
        elif merged.nights_min is not None:
            ref_n = merged.nights_min
        else:
            ref_n = merged.nights_max  # type: ignore[assignment]
        duration_label = f"Options outside your {ref_n}-night request"

        duration_cards: list[dict] = []
        duration_candidates = []
        for cruise in cruises:
            if cruise.cruise_id in shown_ids:
                continue
            if not _passes_non_date_filters(cruise):
                continue
            # Outside the nights band by up to ±3
            if merged.nights_min is not None and merged.nights_max is not None:
                lo = merged.nights_min - 3
                hi = merged.nights_max + 3
                in_expanded = lo <= cruise.nights <= hi
                in_exact = merged.nights_min <= cruise.nights <= merged.nights_max
                outside_exact_but_in_band = in_expanded and not in_exact
            elif merged.nights_min is not None:
                outside_exact_but_in_band = (
                    merged.nights_min - 3 <= cruise.nights < merged.nights_min
                )
            else:  # nights_max only
                outside_exact_but_in_band = (
                    merged.nights_max < cruise.nights <= merged.nights_max + 3
                )

            if not outside_exact_but_in_band:
                continue

            # Select a sailing (relax nothing — just the nights band is relaxed implicitly)
            sailing = _select_sailing(cruise, month=merged.month, return_by=return_by_date)
            if sailing is None:
                # Relax date too (pick any upcoming sailing)
                sailing = _select_sailing(cruise, month=None, return_by=None)
            if sailing is None:
                continue
            duration_candidates.append((cruise, sailing))

        duration_candidates.sort(key=lambda t: t[0].popularity_score, reverse=True)
        for cruise, sailing in duration_candidates[:5]:
            duration_cards.append(_build_near_miss_card(cruise, sailing))
            shown_ids.add(cruise.cruise_id)

        # Zero-match fallback: if ±3 band produced nothing and there are no exact
        # matches, widen to nearest-nights cruises from the full catalog so that
        # R10 (zero-match must never be empty) is always satisfied.
        if not duration_cards and no_exact:
            # Collect all catalog cruises that pass non-date filters and aren't shown
            nearest_candidates = []
            for cruise in cruises:
                if cruise.cruise_id in shown_ids:
                    continue
                if not _passes_non_date_filters(cruise):
                    continue
                # Skip cruises that ARE in the exact band (they would have been shown)
                if merged.nights_min is not None and merged.nights_max is not None:
                    if merged.nights_min <= cruise.nights <= merged.nights_max:
                        continue
                elif merged.nights_min is not None:
                    if cruise.nights >= merged.nights_min:
                        continue
                else:  # nights_max only
                    if cruise.nights <= merged.nights_max:  # type: ignore[operator]
                        continue
                sailing = _select_sailing(cruise, month=merged.month, return_by=return_by_date)
                if sailing is None:
                    sailing = _select_sailing(cruise, month=None, return_by=None)
                if sailing is None:
                    continue
                nearest_candidates.append((cruise, sailing))

            # Sort by proximity to requested nights, then popularity
            ref_nights = ref_n if ref_n is not None else 0
            nearest_candidates.sort(
                key=lambda t: (abs(t[0].nights - ref_nights), -t[0].popularity_score)
            )
            for cruise, sailing in nearest_candidates[:5]:
                duration_cards.append(_build_near_miss_card(cruise, sailing))
                shown_ids.add(cruise.cruise_id)

        if duration_cards:
            sections.append({"label": duration_label, "cards": duration_cards})

    # ---- Section 2: Date shift ±7 days (if month or return_by set) ----
    if merged.month is not None or merged.return_by is not None:
        date_shift_label = "Sailings within a week of your dates"
        date_shift_cards: list[dict] = []
        date_shift_candidates = []

        for cruise in cruises:
            if cruise.cruise_id in shown_ids:
                continue
            if not _passes_non_date_filters(cruise):
                continue
            # Must pass nights filter exactly
            if merged.nights_min is not None and cruise.nights < merged.nights_min:
                continue
            if merged.nights_max is not None and cruise.nights > merged.nights_max:
                continue

            # Try sailings within ±7 days of the constraint boundary
            best_sailing = None
            best_dist = 999999

            for s in cruise.sailings:
                dep = date.fromisoformat(s.departure_date)
                ret = date.fromisoformat(s.return_date)
                if dep < DEMO_ANCHOR:
                    continue

                if merged.month is not None:
                    # Find earliest sailing in adjacent months (month ± 1) or same month diff year
                    # Actually: within ±7 days of the nearest month boundary
                    # Boundary = first day of the month, last day of month
                    from calendar import monthrange
                    year = dep.year
                    m = merged.month
                    # Clamp year: find nearest occurrence of month m
                    # Try same year and next year
                    for try_year in [year - 1, year, year + 1]:
                        if try_year < DEMO_ANCHOR.year:
                            continue
                        try:
                            month_start = date(try_year, m, 1)
                            last_day = monthrange(try_year, m)[1]
                            month_end = date(try_year, m, last_day)
                        except ValueError:
                            continue
                        # Distance from sailing departure to nearest month boundary
                        dist_start = abs((dep - month_start).days)
                        dist_end = abs((dep - month_end).days)
                        dist = min(dist_start, dist_end)
                        # Also require departure is NOT in the target month (those are exact)
                        if dep.month == m and dep.year == try_year:
                            continue
                        if dist <= 7 and dist < best_dist:
                            best_dist = dist
                            best_sailing = s

                if merged.return_by is not None and return_by_date is not None:
                    # Sailings within ±7 days of return_by boundary
                    dist = abs((ret - return_by_date).days)
                    if dist <= 7 and ret > return_by_date and dist < best_dist:
                        best_dist = dist
                        best_sailing = s

            if best_sailing is not None:
                date_shift_candidates.append((cruise, best_sailing))

        date_shift_candidates.sort(key=lambda t: t[0].popularity_score, reverse=True)
        for cruise, sailing in date_shift_candidates[:5]:
            date_shift_cards.append(_build_near_miss_card(cruise, sailing))
            shown_ids.add(cruise.cruise_id)

        if date_shift_cards:
            sections.append({"label": date_shift_label, "cards": date_shift_cards})

    # ---- Section 3: Adjacent region (zero-match only) ----
    if no_exact and merged.region:
        adjacent_label = "Other regions matching your dates"
        adjacent_cards: list[dict] = []
        adjacent_candidates = []

        for cruise in cruises:
            if cruise.cruise_id in shown_ids:
                continue
            # Different region
            if cruise.region.lower() == merged.region.lower():
                continue
            # Must pass non-region, non-date filters
            if merged.embark_port and merged.embark_port.lower() not in cruise.embark_port.lower():
                continue
            if merged.budget_max is not None and cruise.fare_now > merged.budget_max:
                continue
            # Must pass nights filter
            if merged.nights_min is not None and cruise.nights < merged.nights_min:
                continue
            if merged.nights_max is not None and cruise.nights > merged.nights_max:
                continue
            # Select sailing with date constraints
            sailing = _select_sailing(cruise, month=merged.month, return_by=return_by_date)
            if sailing is None:
                # Relax date
                sailing = _select_sailing(cruise, month=None, return_by=None)
            if sailing is None:
                continue
            adjacent_candidates.append((cruise, sailing))

        adjacent_candidates.sort(key=lambda t: t[0].popularity_score, reverse=True)
        for cruise, sailing in adjacent_candidates[:5]:
            adjacent_cards.append(_build_near_miss_card(cruise, sailing))
            shown_ids.add(cruise.cruise_id)

        if adjacent_cards:
            sections.append({"label": adjacent_label, "cards": adjacent_cards})

    return {
        "results": cards,
        "filters": filters,
        "total_matches": total_matches,
        "sections": sections,
        "no_exact": no_exact,
    }
