"""P2 tests — create_draft, set_fare, set_stateroom tools."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.models import Session, Constraints
from app.catalog.loader import load_catalog
from app.tools.draft import create_draft, set_fare, set_stateroom, checkout_entry, remove_draft


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_session(party: int = 2) -> Session:
    """Create a fresh session."""
    return Session(session_id="test-session", party=party)


# Test 4: create_draft 6 times → 6th is refused, len(drafts)==5
def test_create_draft_cap_at_5(catalog):
    """6th create_draft call returns draft_cap error; session has exactly 5 drafts."""
    session = make_session()

    cruise_ids = [
        "denali_explorer",
        "glacier_discovery",
        "alaska_inside_passage",
        "yukon_denali",
        "denali_explorer",  # reuse is fine for cap testing
    ]
    for i, cid in enumerate(cruise_ids, start=1):
        r = create_draft(session, {"cruise_id": cid})
        assert "error" not in r, f"Draft {i} failed: {r}"
        assert len(session.drafts) == i

    # 6th attempt must be refused
    r6 = create_draft(session, {"cruise_id": "glacier_discovery"})
    assert r6.get("error") == "draft_cap", f"Expected draft_cap error, got: {r6}"
    assert "message" in r6, "Error response must include 'message'"

    # Session must still have exactly 5 drafts
    assert len(session.drafts) == 5, f"Expected 5 drafts, got {len(session.drafts)}"


def test_create_draft_sets_active_draft(catalog):
    """create_draft sets active_draft_id to the new draft."""
    session = make_session()
    result = create_draft(session, {"cruise_id": "denali_explorer"})
    assert session.active_draft_id == result["draft_id"]


def test_create_draft_completed_steps_starts_at_1(catalog):
    """New draft has completed_steps=[1]."""
    session = make_session()
    result = create_draft(session, {"cruise_id": "denali_explorer"})
    assert result["completed_steps"] == [1]


# Test 5: set_fare → step 2 added, total increased
def test_set_fare_adds_step_2_and_updates_total(catalog):
    """set_fare('have_it_all') → step 2 in completed_steps, total increased by package delta."""
    session = make_session(party=2)
    cr = create_draft(session, {"cruise_id": "alaska_inside_passage"})
    draft_id = cr["draft_id"]

    total_before = cr["total"]
    assert 1 in cr["completed_steps"]

    result = set_fare(session, {"draft_id": draft_id, "package": "have_it_all"})

    assert "error" not in result, f"set_fare failed: {result}"
    assert 2 in result["completed_steps"], f"Step 2 not in {result['completed_steps']}"

    # have_it_all adds 55 * nights * party to total
    # alaska_inside_passage: 7 nights, party=2 → delta = 55 * 7 * 2 = 770
    total_after = result["total"]
    expected_delta = 55 * 7 * 2  # 770
    assert total_after == total_before + expected_delta, (
        f"Total delta expected {expected_delta}, got {total_after - total_before}"
    )
    assert result["total_delta"] == expected_delta


def test_set_fare_good_to_go_no_delta(catalog):
    """set_fare('good_to_go') on a good_to_go draft → total unchanged, step 2 added."""
    session = make_session()
    cr = create_draft(session, {"cruise_id": "alaska_inside_passage"})
    draft_id = cr["draft_id"]
    total_before = cr["total"]

    result = set_fare(session, {"draft_id": draft_id, "package": "good_to_go"})
    assert "error" not in result
    assert 2 in result["completed_steps"]
    assert result["total"] == total_before  # no change


# Test 6: set_stateroom(verandah, mid) → step 3, total += 486/pp
def test_set_stateroom_verandah_mid_adds_step_3_and_486_per_person(catalog):
    """set_stateroom(verandah, mid) → step 3 in completed_steps, total reflects +486/pp."""
    session = make_session(party=2)
    cr = create_draft(session, {"cruise_id": "alaska_inside_passage"})
    draft_id = cr["draft_id"]
    total_before = cr["total"]

    result = set_stateroom(session, {
        "draft_id": draft_id,
        "category": "Verandah",
        "location": "mid",
    })

    assert "error" not in result, f"set_stateroom failed: {result}"
    assert 3 in result["completed_steps"], f"Step 3 not in {result['completed_steps']}"

    # Verandah delta = 486/person, party=2 → total delta = 486*2 = 972
    expected_delta = 486 * 2
    total_after = result["total"]
    assert total_after == total_before + expected_delta, (
        f"Expected total delta {expected_delta}, got {total_after - total_before}"
    )
    assert result["total_delta"] == expected_delta


# D2: lowercase category matches case-insensitively and prices the delta
def test_set_stateroom_lowercase_verandah_matches_and_prices(catalog):
    """set_stateroom(d,'verandah','mid') lowercase → succeeds, step 3 added, +486/pp delta."""
    session = make_session(party=2)
    cr = create_draft(session, {"cruise_id": "alaska_inside_passage"})
    draft_id = cr["draft_id"]
    total_before = cr["total"]

    result = set_stateroom(session, {
        "draft_id": draft_id,
        "category": "verandah",  # lowercase, as an LLM will send
        "location": "mid",
    })

    assert "error" not in result, f"set_stateroom failed: {result}"
    assert 3 in result["completed_steps"], f"Step 3 not in {result['completed_steps']}"

    # Verandah delta = 486/person, party=2 → total delta = 486*2 = 972
    expected_delta = 486 * 2
    assert result["total"] == total_before + expected_delta, (
        f"Expected total delta {expected_delta}, got {result['total'] - total_before}"
    )
    assert result["total_delta"] == expected_delta
    # Stored/returned category is canonical catalog casing.
    assert result["stateroom"]["category"] == "Verandah"


# D2: bogus category returns invalid_category error, step 3 NOT added
def test_set_stateroom_invalid_category_errors_and_no_step_3(catalog):
    """set_stateroom with a bogus category → invalid_category error; step 3 NOT added, not stored."""
    session = make_session(party=2)
    cr = create_draft(session, {"cruise_id": "alaska_inside_passage"})
    draft_id = cr["draft_id"]
    total_before = cr["total"]

    result = set_stateroom(session, {
        "draft_id": draft_id,
        "category": "penthouse_deluxe",  # not a real catalog category
        "location": "mid",
    })

    assert result.get("error") == "invalid_category", f"Expected invalid_category, got: {result}"
    assert "message" in result

    # Step 3 must NOT be marked and nothing stored/repriced.
    draft = next(d for d in session.drafts if d.draft_id == draft_id)
    assert 3 not in draft.completed_steps, f"Step 3 wrongly added: {draft.completed_steps}"
    assert draft.stateroom.category == "Inside", "Bogus category must not overwrite stored stateroom"
    assert draft.total == total_before, "Total must be unchanged after an invalid category"


# Test 7: checkout_entry == 4 for completed_steps=[1,2,3]
def test_checkout_entry_is_4_after_steps_1_2_3(catalog):
    """Draft with completed_steps=[1,2,3] → checkout_entry(draft)==4."""
    from app.models import Draft, DraftStateroom

    draft = Draft(
        draft_id="test-checkout",
        cruise_id="alaska_inside_passage",
        label="Test",
        fare_package="good_to_go",
        stateroom=DraftStateroom(category="Inside"),
        completed_steps=[1, 2, 3],
    )

    entry = checkout_entry(draft)
    assert entry == 4, f"Expected checkout_entry=4, got {entry}"


def test_checkout_entry_via_set_fare_and_stateroom(catalog):
    """After steps 1,2,3 are done via tools, checkout_entry==4."""
    session = make_session()
    cr = create_draft(session, {"cruise_id": "alaska_inside_passage"})
    draft_id = cr["draft_id"]

    set_fare(session, {"draft_id": draft_id, "package": "good_to_go"})
    result = set_stateroom(session, {"draft_id": draft_id, "category": "Inside"})

    assert result["checkout_entry"] == 4


def test_create_draft_invalid_cruise(catalog):
    """create_draft with unknown cruise_id returns error."""
    session = make_session()
    result = create_draft(session, {"cruise_id": "nonexistent_cruise"})
    assert "error" in result
    assert result["error"] == "cruise_not_found"


# ---------------------------------------------------------------------------
# remove_draft tests
# ---------------------------------------------------------------------------

def test_remove_draft_removes_and_returns_remaining(catalog):
    """remove_draft removes the draft and returns remaining count."""
    session = make_session()
    r1 = create_draft(session, {"cruise_id": "denali_explorer"})
    r2 = create_draft(session, {"cruise_id": "glacier_discovery"})
    draft_id = r1["draft_id"]

    result = remove_draft(session, {"draft_id": draft_id})
    assert result.get("removed") is True
    assert result.get("draft_id") == draft_id
    assert result.get("remaining") == 1
    assert not any(d.draft_id == draft_id for d in session.drafts)


def test_remove_active_draft_reassigns_active(catalog):
    """Removing the active draft sets active_draft_id to another draft or None."""
    session = make_session()
    r1 = create_draft(session, {"cruise_id": "denali_explorer"})
    r2 = create_draft(session, {"cruise_id": "glacier_discovery"})
    # active is now r2 (last created)
    active_id = session.active_draft_id
    assert active_id == r2["draft_id"]

    result = remove_draft(session, {"draft_id": active_id})
    assert result.get("removed") is True
    # active should reassign to the remaining draft
    assert session.active_draft_id == r1["draft_id"]


def test_remove_only_draft_sets_active_none(catalog):
    """Removing the only draft sets active_draft_id to None."""
    session = make_session()
    r1 = create_draft(session, {"cruise_id": "denali_explorer"})
    draft_id = r1["draft_id"]

    result = remove_draft(session, {"draft_id": draft_id})
    assert result.get("removed") is True
    assert result.get("remaining") == 0
    assert session.active_draft_id is None


def test_remove_draft_unknown_id_returns_error(catalog):
    """remove_draft with unknown draft_id returns draft_not_found error."""
    session = make_session()
    result = remove_draft(session, {"draft_id": "nonexistent-id"})
    assert result.get("error") == "draft_not_found"
    assert "message" in result


def test_create_draft_five_allowed_sixth_rejected(catalog):
    """5 drafts allowed; 6th returns draft_cap."""
    session = make_session()
    cruise_ids = [
        "denali_explorer",
        "glacier_discovery",
        "alaska_inside_passage",
        "yukon_denali",
        "denali_explorer",
    ]
    for cid in cruise_ids:
        r = create_draft(session, {"cruise_id": cid})
        assert "error" not in r, f"Failed: {r}"
    assert len(session.drafts) == 5

    r6 = create_draft(session, {"cruise_id": "glacier_discovery"})
    assert r6.get("error") == "draft_cap"
