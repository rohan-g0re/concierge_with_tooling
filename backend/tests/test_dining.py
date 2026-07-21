"""P3 tests — list_dining, reserve_dining tools."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.models import Session
from app.catalog.loader import load_catalog
from app.tools.draft import create_draft, set_fare, set_stateroom
from app.tools.dining import list_dining, reserve_dining


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_session(party: int = 2) -> Session:
    return Session(session_id="test-dining-session", party=party)


def make_denali_draft(session: Session) -> str:
    """Create a denali_explorer draft and return draft_id."""
    result = create_draft(session, {"cruise_id": "denali_explorer"})
    assert "error" not in result, f"create_draft failed: {result}"
    draft_id = result["draft_id"]
    set_fare(session, {"draft_id": draft_id, "package": "have_it_all"})
    set_stateroom(session, {"draft_id": draft_id, "category": "Verandah", "location": "Midship"})
    return draft_id


# P3 Test 1: list_dining → each venue has availability for nights 1..N;
#            night with capacity_remaining==0 marked sold_out
def test_list_dining_availability_grid_and_sold_out(catalog):
    """list_dining returns nights 1..N per venue; sold-out nights are marked sold_out."""
    session = make_session()
    result = list_dining(session, {"cruise_id": "denali_explorer"})

    assert "error" not in result, f"list_dining failed: {result}"
    assert "venues" in result
    assert len(result["venues"]) > 0, "Expected at least one venue"

    # Find Saffron venue
    saffron = next((v for v in result["venues"] if v["venue_id"] == "saffron"), None)
    assert saffron is not None, "Saffron venue not found"

    nights = saffron["nights"]
    night_nums = [n["night"] for n in nights]

    # Nights should cover 1..N (denali_explorer is 12 nights)
    assert night_nums == list(range(1, 13)), f"Expected nights 1..12, got {night_nums}"

    # Nights 3 and 8 are sold out in catalog (capacity_remaining==0)
    status_map = {n["night"]: n["status"] for n in nights}
    assert status_map[3] == "sold_out", f"Night 3 should be sold_out, got {status_map[3]}"
    assert status_map[8] == "sold_out", f"Night 8 should be sold_out, got {status_map[8]}"

    # Night 5 should be available (has capacity)
    assert status_map[5] == "available", f"Night 5 should be available, got {status_map[5]}"


def test_list_dining_venue_has_price_and_cuisine(catalog):
    """list_dining venues include cuisine tags, price_per_guest, price_formatted."""
    session = make_session()
    result = list_dining(session, {"cruise_id": "denali_explorer"})

    saffron = next((v for v in result["venues"] if v["venue_id"] == "saffron"), None)
    assert saffron is not None
    assert isinstance(saffron["cuisine"], list)
    assert len(saffron["cuisine"]) > 0
    assert isinstance(saffron["price_per_guest"], int)
    assert "US$" in saffron["price_formatted"]


# P3 Test 2: reserve_dining(d, 'saffron', 5) → appears in draft.dining; capacity decremented
def test_reserve_dining_success_appears_in_draft_and_decrements_capacity(catalog):
    """reserve_dining appends to draft.dining and decrements session-scoped capacity."""
    session = make_session()
    draft_id = make_denali_draft(session)

    # Get capacity before
    before = list_dining(session, {"cruise_id": "denali_explorer"})
    saffron_before = next(v for v in before["venues"] if v["venue_id"] == "saffron")
    night5_before = next(n for n in saffron_before["nights"] if n["night"] == 5)
    assert night5_before["status"] == "available"

    result = reserve_dining(session, {"draft_id": draft_id, "venue_id": "saffron", "night": 5})

    assert "error" not in result, f"reserve_dining failed: {result}"
    assert "saffron:night_5" in result["dining"], f"Reservation not in dining: {result['dining']}"
    assert 4 in result["completed_steps"], f"Step 4 not in {result['completed_steps']}"

    # Draft object should also have it
    draft = next(d for d in session.drafts if d.draft_id == draft_id)
    assert "saffron:night_5" in draft.dining

    # Now list_dining should show night 5 as "reserved"
    after = list_dining(session, {"cruise_id": "denali_explorer"})
    saffron_after = next(v for v in after["venues"] if v["venue_id"] == "saffron")
    night5_after = next(n for n in saffron_after["nights"] if n["night"] == 5)
    assert night5_after["status"] == "reserved", f"Night 5 should be reserved after booking, got {night5_after['status']}"


def test_reserve_dining_capacity_decremented_in_session_overlay(catalog):
    """Capacity decrement is tracked in session overlay; another session sees original."""
    from app.tools.dining import _get_overlay, _capacity_for

    session_a = Session(session_id="cap-test-a", party=2)
    session_b = Session(session_id="cap-test-b", party=2)

    draft_id_a = make_denali_draft(session_a)

    # Get catalog capacity for saffron night 5 before any reservation
    cat = get_catalog()
    catalog_venues = [v for v in cat["dining"] if v.cruise_id == "denali_explorer"]
    cap_before = _capacity_for(session_a, "denali_explorer", "saffron", 5, catalog_venues)

    reserve_dining(session_a, {"draft_id": draft_id_a, "venue_id": "saffron", "night": 5})

    # Session A should have decremented capacity
    cap_after_a = _capacity_for(session_a, "denali_explorer", "saffron", 5, catalog_venues)
    assert cap_after_a == cap_before - 1, f"Expected {cap_before - 1}, got {cap_after_a}"

    # Session B should still see original catalog capacity (no overlay)
    cap_b = _capacity_for(session_b, "denali_explorer", "saffron", 5, catalog_venues)
    assert cap_b == cap_before, f"Session B capacity should be unchanged: expected {cap_before}, got {cap_b}"


def get_catalog():
    from app.catalog.loader import get_catalog as _get_catalog
    return _get_catalog()


# P3 Test 3: reserve_dining where night is sold out → rejected {error:'sold_out'}
def test_reserve_dining_sold_out_rejected(catalog):
    """reserve_dining on a sold-out night returns {error:'sold_out'}."""
    session = make_session()
    draft_id = make_denali_draft(session)

    # Night 3 is sold out in catalog (capacity_remaining==0)
    result = reserve_dining(session, {"draft_id": draft_id, "venue_id": "saffron", "night": 3})

    assert result.get("error") == "sold_out", f"Expected sold_out error, got: {result}"
    assert "message" in result

    # Draft dining should still be empty
    draft = next(d for d in session.drafts if d.draft_id == draft_id)
    assert "saffron:night_3" not in draft.dining


# P3 Test 4: Reserve same (venue,night) twice → second rejected {error:'double_book'}
def test_reserve_dining_double_book_rejected(catalog):
    """Second reserve of same (venue, night) returns {error:'double_book'}."""
    session = make_session()
    draft_id = make_denali_draft(session)

    # First reservation — should succeed
    r1 = reserve_dining(session, {"draft_id": draft_id, "venue_id": "saffron", "night": 5})
    assert "error" not in r1, f"First reserve failed: {r1}"

    # Second reservation — should be rejected
    r2 = reserve_dining(session, {"draft_id": draft_id, "venue_id": "saffron", "night": 5})
    assert r2.get("error") == "double_book", f"Expected double_book error, got: {r2}"
    assert "message" in r2


def test_reserve_dining_updates_total(catalog):
    """reserve_dining updates draft total by price_per_guest * party."""
    session = make_session(party=2)
    draft_id = make_denali_draft(session)

    draft = next(d for d in session.drafts if d.draft_id == draft_id)
    total_before = draft.total

    result = reserve_dining(session, {"draft_id": draft_id, "venue_id": "saffron", "night": 5})
    assert "error" not in result

    # Saffron price_per_guest = 38, party = 2 → delta = 76
    assert result["total"] == total_before + 76, (
        f"Expected total {total_before + 76}, got {result['total']}"
    )
