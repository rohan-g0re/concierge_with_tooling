"""P2 tests — get_itinerary tool."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.models import Session, Constraints
from app.catalog.loader import load_catalog
from app.tools.itinerary import get_itinerary


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_session() -> Session:
    return Session(session_id="test-session")


# Test 8: get_itinerary day count + ports
def test_itinerary_day_count_and_ports(catalog):
    """Itinerary for denali_explorer: each day has a port field."""
    session = make_session()
    result = get_itinerary(session, {"cruise_id": "denali_explorer"})

    assert "error" not in result, f"Unexpected error: {result}"
    assert result["cruise_id"] == "denali_explorer"

    days = result["days"]
    assert len(days) > 0, "Expected at least one itinerary day"
    assert result["day_count"] == len(days)

    # Every day must have a non-empty port
    for day in days:
        assert "port" in day, f"Day {day.get('day')} missing 'port' field"
        assert day["port"], f"Day {day.get('day')} has empty port"
        assert "day" in day, f"Missing 'day' label"


def test_itinerary_cruise_not_found():
    """Non-existent cruise_id returns error dict."""
    session = make_session()
    result = get_itinerary(session, {"cruise_id": "nonexistent_cruise"})
    assert "error" in result
    assert result["error"] == "cruise_not_found"


def test_itinerary_missing_cruise_id():
    """Missing cruise_id returns error dict."""
    session = make_session()
    result = get_itinerary(session, {})
    assert "error" in result
    assert result["error"] == "missing_cruise_id"


def test_itinerary_alaska_inside_passage(catalog):
    """alaska_inside_passage itinerary also has day+port entries."""
    session = make_session()
    result = get_itinerary(session, {"cruise_id": "alaska_inside_passage"})

    if "error" in result:
        pytest.skip(f"No itinerary data for alaska_inside_passage: {result}")

    days = result["days"]
    for day in days:
        assert day["port"], f"Missing port in {day}"
