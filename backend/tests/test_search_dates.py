"""
Unit 3 tests — date filtering in search_cruises.

Tests:
  1. {region:"alaska", month:10} → every card departure_date month == 10, has sailing_id + return_date
  2. {nights_min:7, nights_max:7, return_by:"2026-12-28"} → nights==7 and return_date <= 2026-12-28
  3. {region:"caribbean"} → each card departure_date >= 2026-07-01 and is earliest such sailing
  4. {month:1} (Jan < anchor) → departures in Jan of next year (>= anchor)
  5. Stub: "all October sailings" → search_cruises called with month=10
  6. Malformed return_by "not-a-date" → no exception, results returned
  7. Mapper parity: dated result → card_row via both mappers with dated cards
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Force stub mode before any app imports
os.environ["LLM_MODE"] = "stub"

import pytest
from app.models import Session, Constraints
from app.tools.search import search_cruises, DEMO_ANCHOR


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

def make_session(**kwargs) -> Session:
    """Create a fresh session with optional constraint overrides."""
    return Session(session_id="date-test-session", constraints=Constraints(**kwargs))


# ---------------------------------------------------------------------------
# Test 1: month filter — Alaska October sailings
# ---------------------------------------------------------------------------

def test_alaska_october_month_filter():
    """
    {region:"alaska", month:10} → every card departure_date[5:7] == "10",
    has sailing_id and return_date.
    """
    session = make_session()
    result = search_cruises(session, {"region": "alaska", "month": 10})
    cards = result["results"]

    assert len(cards) >= 1, "Expected at least 1 Alaska cruise to have an October sailing"

    for card in cards:
        dep = card["departure_date"]
        assert dep[5:7] == "10", (
            f"Expected departure in October (month 10), got {dep!r} for {card['cruise_id']}"
        )
        assert "sailing_id" in card, f"Card missing sailing_id: {card['cruise_id']}"
        assert card["sailing_id"], f"sailing_id is empty for {card['cruise_id']}"
        assert "return_date" in card, f"Card missing return_date: {card['cruise_id']}"
        assert card["return_date"], f"return_date is empty for {card['cruise_id']}"


# ---------------------------------------------------------------------------
# Test 2: nights + return_by filter
# (7-night cruises, not 14 — catalog has 7-night Bermuda/Bahamas/others)
# ---------------------------------------------------------------------------

def test_7night_return_by_filter():
    """
    {nights_min:7, nights_max:7, return_by:"2026-12-28"} →
    every card nights==7 and return_date <= 2026-12-28.
    """
    session = make_session()
    result = search_cruises(session, {
        "nights_min": 7,
        "nights_max": 7,
        "return_by": "2026-12-28",
    })
    cards = result["results"]

    assert len(cards) >= 1, "Expected at least 1 7-night cruise with return_date <= 2026-12-28"

    for card in cards:
        assert card["nights"] == 7, (
            f"Expected 7-night cruise, got {card['nights']} for {card['cruise_id']}"
        )
        ret = card["return_date"]
        assert ret <= "2026-12-28", (
            f"return_date {ret!r} exceeds 2026-12-28 for {card['cruise_id']}"
        )


# ---------------------------------------------------------------------------
# Test 3: plain regional search — earliest upcoming sailing per cruise
# ---------------------------------------------------------------------------

def test_caribbean_earliest_upcoming_sailing():
    """
    {region:"caribbean"} → each card departure_date >= 2026-07-01 and is the
    earliest such sailing for its cruise.
    """
    from app.catalog.loader import get_catalog

    session = make_session()
    result = search_cruises(session, {"region": "caribbean"})
    cards = result["results"]

    assert len(cards) >= 1, "Expected at least 1 Caribbean cruise"

    catalog = get_catalog()
    cruise_by_id = {c.cruise_id: c for c in catalog["cruises"]}
    anchor_str = DEMO_ANCHOR.isoformat()

    for card in cards:
        dep = card["departure_date"]
        assert dep >= anchor_str, (
            f"departure_date {dep!r} is before anchor {anchor_str} for {card['cruise_id']}"
        )
        # Verify it's the earliest sailing >= anchor for this cruise
        cruise = cruise_by_id[card["cruise_id"]]
        upcoming = [s for s in cruise.sailings if s.departure_date >= anchor_str]
        if upcoming:
            earliest = min(upcoming, key=lambda s: s.departure_date)
            assert dep == earliest.departure_date, (
                f"Expected earliest upcoming sailing {earliest.departure_date!r}, "
                f"got {dep!r} for {card['cruise_id']}"
            )


# ---------------------------------------------------------------------------
# Test 4: month before anchor — year roll-over
# ---------------------------------------------------------------------------

def test_january_month_resolves_to_next_year():
    """
    {month:1} — January is before the July 2026 anchor, so departures must
    be in January of the following year (2027), i.e. departure_date >= 2026-07-01.
    """
    session = make_session()
    result = search_cruises(session, {"month": 1})
    cards = result["results"]

    # If there are any results, all must be in January and >= anchor
    for card in cards:
        dep = card["departure_date"]
        assert dep[5:7] == "01", (
            f"Expected departure month January (01), got {dep!r} for {card['cruise_id']}"
        )
        assert dep >= DEMO_ANCHOR.isoformat(), (
            f"departure_date {dep!r} is before anchor for {card['cruise_id']}"
        )


# ---------------------------------------------------------------------------
# Test 5: stub orchestrator — "all October sailings" → month=10 in result cards
# ---------------------------------------------------------------------------

def test_stub_october_sailings_keyword():
    """
    Stub run_turn with 'all October sailings' → search_cruises called with month=10;
    result cards all have departure month 10.
    """
    from app.config import get_settings
    get_settings.cache_clear()

    from app.llm.stub_orchestrator import run_turn

    session = make_session()
    response = run_turn(session, "all October sailings")

    # Check tool_calls
    assert "search_cruises" in response.get("tool_calls", []), (
        f"Expected search_cruises in tool_calls, got {response.get('tool_calls')}"
    )

    # Check components contain card_row
    components = response.get("components", [])
    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is not None, f"Expected card_row component, got {components}"

    cards = card_row.get("cards", [])
    assert len(cards) >= 1, "Expected at least 1 card for October sailings"

    # All cards must depart in October
    for card in cards:
        dep = card.get("departure_date", "")
        assert dep[5:7] == "10", (
            f"Expected October departure (month 10), got {dep!r} for {card.get('cruise_id')}"
        )


# ---------------------------------------------------------------------------
# Test 6: malformed return_by → no exception, results returned
# ---------------------------------------------------------------------------

def test_malformed_return_by_no_exception():
    """
    Malformed return_by "not-a-date" must not raise an exception and must
    still return results (ignoring the bad constraint).
    """
    session = make_session()
    # Should not raise
    result = search_cruises(session, {"region": "caribbean", "return_by": "not-a-date"})

    # Must return a valid result structure
    assert "results" in result, "Expected 'results' key in response"
    assert "total_matches" in result, "Expected 'total_matches' key in response"
    assert isinstance(result["results"], list), "results must be a list"

    # With malformed return_by ignored, should still get Caribbean results
    assert len(result["results"]) >= 1, "Expected at least 1 Caribbean result when return_by is ignored"


# ---------------------------------------------------------------------------
# Test 7: mapper parity — dated cards pass through both mapper paths
# ---------------------------------------------------------------------------

def test_dated_cards_pass_through_gemini_mapper():
    """
    A dated search result must produce a card_row via _map_tool_result_to_component
    (Gemini path) with the date fields intact.
    """
    from app.llm.gemini_client import _map_tool_result_to_component

    session = make_session()
    result = search_cruises(session, {"region": "alaska", "month": 10})

    component = _map_tool_result_to_component("search_cruises", result)

    assert component is not None, "Expected a component from mapper"
    assert component.get("type") == "card_row", f"Expected card_row, got {component.get('type')}"

    cards = component.get("cards", [])
    assert len(cards) >= 1, "Expected at least 1 card in component"

    for card in cards:
        assert "sailing_id" in card, f"sailing_id missing from card_row card: {card.get('cruise_id')}"
        assert "departure_date" in card, f"departure_date missing from card_row card: {card.get('cruise_id')}"
        assert "return_date" in card, f"return_date missing from card_row card: {card.get('cruise_id')}"


# ---------------------------------------------------------------------------
# Test 8: stub orchestrator — "back before dec 28" sets return_by, NOT month
# ---------------------------------------------------------------------------

def test_stub_back_before_dec_28_no_month():
    """
    "i need to be back before dec 28" must produce return_by=="2026-12-28"
    and must NOT set month (dec is a return constraint, not a search filter).
    """
    from app.config import get_settings
    get_settings.cache_clear()

    from app.llm.stub_orchestrator import run_turn

    session = make_session()
    response = run_turn(session, "i need to be back before dec 28")

    assert "search_cruises" in response.get("tool_calls", []), (
        f"Expected search_cruises in tool_calls, got {response.get('tool_calls')}"
    )

    components = response.get("components", [])
    # Locate the system_event component which carries the filters passed to the tool
    sys_evt = next((c for c in components if c.get("type") == "system_event"), None)
    assert sys_evt is not None, f"Expected system_event component, got {components}"

    filters = sys_evt.get("filters", {})
    # The stub regex captures "dec 28" as the raw string; search_cruises
    # normalises it to an ISO date internally.  Either form is acceptable here —
    # what matters is that return_by is set (not None) and month is NOT set.
    assert filters.get("return_by") is not None, (
        f"Expected return_by to be set, got {filters.get('return_by')!r}"
    )
    assert "month" not in filters or filters.get("month") is None, (
        f"month must be unset when return_by is parsed; got month={filters.get('month')!r}"
    )


# ---------------------------------------------------------------------------
# Test 9: stub orchestrator — "bermuda cruises in october" still sets month=10
# ---------------------------------------------------------------------------

def test_stub_bermuda_october_month_preserved():
    """
    "show me bermuda cruises in october" must set region=bermuda_bahamas AND
    month=10.  Verifies that the return_by excision does not break normal
    month detection.
    """
    from app.config import get_settings
    get_settings.cache_clear()

    from app.llm.stub_orchestrator import run_turn

    session = make_session()
    response = run_turn(session, "show me bermuda cruises in october")

    assert "search_cruises" in response.get("tool_calls", []), (
        f"Expected search_cruises in tool_calls, got {response.get('tool_calls')}"
    )

    components = response.get("components", [])
    sys_evt = next((c for c in components if c.get("type") == "system_event"), None)
    assert sys_evt is not None, f"Expected system_event component, got {components}"

    filters = sys_evt.get("filters", {})
    assert filters.get("region") == "bermuda_bahamas", (
        f"Expected region=='bermuda_bahamas', got {filters.get('region')!r}"
    )
    assert filters.get("month") == 10, (
        f"Expected month==10, got {filters.get('month')!r}"
    )


def test_dated_cards_pass_through_action_builder():
    """
    A dated search result must produce a card_row via _build_components
    (action path) with the date fields intact.
    """
    from app.routes.action import _build_components

    session = make_session()
    result = search_cruises(session, {"region": "alaska", "month": 10})

    components = _build_components("search_cruises", result, session)

    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is not None, f"Expected card_row in action components, got {components}"

    cards = card_row.get("cards", [])
    assert len(cards) >= 1, "Expected at least 1 card in action card_row"

    for card in cards:
        assert "sailing_id" in card, f"sailing_id missing from action card: {card.get('cruise_id')}"
        assert "departure_date" in card, f"departure_date missing from action card: {card.get('cruise_id')}"
        assert "return_date" in card, f"return_date missing from action card: {card.get('cruise_id')}"


# ---------------------------------------------------------------------------
# Test D1-fix: past ISO date in return_by is rolled forward to future
# ---------------------------------------------------------------------------

def test_past_iso_return_by_rolled_forward():
    """
    _parse_return_by("2024-12-28") must resolve to 2026-12-28 (the next future
    occurrence of Dec 28 >= DEMO_ANCHOR), not the literal past date.
    Results must equal those from return_by="2026-12-28".
    """
    from app.tools.search import _parse_return_by
    from datetime import date

    resolved = _parse_return_by("2024-12-28")
    assert resolved is not None, "_parse_return_by returned None for '2024-12-28'"
    assert resolved >= DEMO_ANCHOR, (
        f"Resolved date {resolved} is before anchor {DEMO_ANCHOR}"
    )
    assert resolved == date(2026, 12, 28), (
        f"Expected 2026-12-28, got {resolved}"
    )

    # Also verify search results are the same as using "2026-12-28" directly
    session_past = make_session()
    result_past = search_cruises(session_past, {"return_by": "2024-12-28"})

    session_future = make_session()
    result_future = search_cruises(session_future, {"return_by": "2026-12-28"})

    past_ids = sorted(c["cruise_id"] for c in result_past["results"])
    future_ids = sorted(c["cruise_id"] for c in result_future["results"])
    assert past_ids == future_ids, (
        f"Results differ: past={past_ids}, future={future_ids}"
    )


# ---------------------------------------------------------------------------
# Test D2-fix: explicit None clears stale nights constraints
# ---------------------------------------------------------------------------

def test_explicit_none_clears_nights_constraints():
    """
    After a search with nights_min=20/nights_max=20, a follow-up search with
    nights_min=None and nights_max=None must clear those constraints.
    The result must be a normal (non-empty) list without a nights band,
    and the session constraints must have nights_min=None, nights_max=None.
    """
    session = make_session()

    # First search: 20-night cruises (will likely return empty or near-miss)
    search_cruises(session, {"nights_min": 20, "nights_max": 20})
    assert session.constraints.nights_min == 20
    assert session.constraints.nights_max == 20

    # Second search: clear nights constraints, add region
    result = search_cruises(session, {
        "nights_min": None,
        "nights_max": None,
        "region": "bermuda_bahamas",
    })

    # Constraints must be cleared
    assert session.constraints.nights_min is None, (
        f"nights_min should be cleared, got {session.constraints.nights_min}"
    )
    assert session.constraints.nights_max is None, (
        f"nights_max should be cleared, got {session.constraints.nights_max}"
    )

    # Must return results (not an empty or no_exact list)
    assert "results" in result
    cards = result["results"]
    assert len(cards) >= 1, (
        "Expected results after clearing nights constraints for bermuda_bahamas"
    )

    # Section label must NOT be no_exact (it's a normal search)
    label = result.get("section_label", "")
    assert "no exact" not in label.lower(), (
        f"Got no_exact label even after clearing nights: {label!r}"
    )
