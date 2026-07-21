"""P2 tests — search_cruises tool."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.models import Session, Constraints
from app.catalog.loader import load_catalog
from app.tools.search import search_cruises


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_session(**kwargs) -> Session:
    """Create a fresh session with optional constraint overrides."""
    return Session(session_id="test-session", constraints=Constraints(**kwargs))


# Test 1: search_cruises({region:'alaska'}) → ≤5 cards, sorted by popularity desc
def test_alaska_returns_at_most_5(catalog):
    session = make_session()
    result = search_cruises(session, {"region": "alaska"})
    cards = result["results"]
    assert len(cards) <= 5, f"Expected ≤5 cards, got {len(cards)}"
    # There are 8 Alaska cruises, so exactly 5 should be returned
    assert len(cards) == 5


def test_alaska_sorted_by_popularity_desc(catalog):
    session = make_session()
    result = search_cruises(session, {"region": "alaska"})
    cards = result["results"]
    assert len(cards) > 0
    scores = [c["popularity_score"] for c in cards]
    assert scores == sorted(scores, reverse=True), f"Not sorted desc: {scores}"
    # First card is highest popularity
    assert cards[0]["popularity_score"] == max(scores)


def test_alaska_first_is_denali(catalog):
    """denali_explorer has popularity=0.95, highest among Alaska."""
    session = make_session()
    result = search_cruises(session, {"region": "alaska"})
    assert result["results"][0]["cruise_id"] == "denali_explorer"


# Test 2: Compound filter (alaska, 6-8 nights, Seattle, budget<4000)
def test_compound_4_constraint_filter(catalog):
    """Compound alaska+nights+port+budget filter: only alaska_inside_passage matches."""
    session = make_session()
    result = search_cruises(session, {
        "region": "alaska",
        "nights_min": 6,
        "nights_max": 8,
        "embark_port": "Seattle",
        "budget_max": 4000,
    })
    cards = result["results"]

    # Verify all results satisfy all 4 constraints
    for card in cards:
        assert card["region"] == "alaska", f"Non-alaska in results: {card['cruise_id']}"
        assert 6 <= card["nights"] <= 8, f"Nights {card['nights']} out of range: {card['cruise_id']}"
        assert "Seattle" in card["embark_port"], f"Non-Seattle port: {card['cruise_id']}"
        assert card["fare_now_raw"] <= 4000, f"fare_now {card['fare_now_raw']} > 4000: {card['cruise_id']}"

    # alaska_inside_passage is the only match
    ids = [c["cruise_id"] for c in cards]
    assert "alaska_inside_passage" in ids, "alaska_inside_passage should match"

    # Verify exclusions: non-matching cruises are not present
    assert "denali_explorer" not in ids, "denali_explorer has 12 nights, should be excluded"
    assert "glacier_discovery" not in ids, "glacier_discovery is Vancouver, should be excluded"
    assert "great_alaskan_explorer" not in ids, "great_alaskan_explorer has 14 nights, should be excluded"


# Test 3: Refinement composes — subset + nights≥10
def test_refinement_composes(catalog):
    """After Alaska search (8 total), apply nights_min=10 → subset, all nights>=10."""
    session = make_session()

    # First search: Alaska only
    result1 = search_cruises(session, {"region": "alaska"})
    prior_ids = {c["cruise_id"] for c in result1["results"]}
    # Constraints now have region=alaska
    assert session.constraints.region == "alaska"

    # Refinement: add nights_min=10 — this merges with existing alaska constraint
    result2 = search_cruises(session, {"nights_min": 10})
    refined_ids = {c["cruise_id"] for c in result2["results"]}
    refined_cards = result2["results"]

    # All refined results have nights >= 10
    for card in refined_cards:
        assert card["nights"] >= 10, f"Cruise {card['cruise_id']} has {card['nights']} nights, expected >= 10"

    # Refined set is subset of (or equal to) the full Alaska set (all still alaska)
    alaska_ids = {
        c.cruise_id for c in catalog["cruises"] if c.region == "alaska"
    }
    for cruise_id in refined_ids:
        assert cruise_id in alaska_ids, f"{cruise_id} is not an Alaska cruise"

    # Verify constraints composed (region still alaska, nights_min now 10)
    assert session.constraints.region == "alaska"
    assert session.constraints.nights_min == 10
