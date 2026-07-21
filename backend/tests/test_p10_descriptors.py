"""P10 tests — fare_tiles and stateroom_picker descriptor builders."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.models import Session
from app.tools.draft import create_draft, set_fare
from app.routes.action import _fare_tiles_options, _append_fare_tiles, _append_stateroom_picker


def make_session(party: int = 2) -> Session:
    return Session(session_id="test-p10", party=party)


# --- fare_tiles descriptor shape ---

def test_fare_tiles_options_shape():
    """_fare_tiles_options returns 2 options with correct ids."""
    options = _fare_tiles_options()
    assert len(options) == 2
    ids = [o["id"] for o in options]
    assert "good_to_go" in ids
    assert "have_it_all" in ids


def test_fare_tiles_have_it_all_has_badge():
    """have_it_all option has badge='Recommended'."""
    options = _fare_tiles_options()
    sig = next(o for o in options if o["id"] == "have_it_all")
    assert sig.get("badge") == "Recommended"


def test_fare_tiles_have_it_all_has_delta_per_day():
    """have_it_all option has delta_per_day containing '55'."""
    options = _fare_tiles_options()
    sig = next(o for o in options if o["id"] == "have_it_all")
    assert "55" in sig.get("delta_per_day", "")


def test_fare_tiles_amenities_present():
    """Both options have non-empty amenities lists."""
    options = _fare_tiles_options()
    for opt in options:
        assert isinstance(opt.get("amenities"), list)
        assert len(opt["amenities"]) > 0


def test_append_fare_tiles_after_create_draft():
    """_append_fare_tiles appends a fare_tiles descriptor with correct draft_id."""
    components: list = []
    result = {"draft_id": "test-draft-123"}
    session = make_session()
    _append_fare_tiles(components, result, session)
    assert len(components) == 1
    assert components[0]["type"] == "fare_tiles"
    assert components[0]["draft_id"] == "test-draft-123"
    assert "options" in components[0]


def test_append_fare_tiles_no_draft_id_does_nothing():
    """_append_fare_tiles with no draft_id does not append."""
    components: list = []
    _append_fare_tiles(components, {}, make_session())
    assert components == []


# --- stateroom_picker descriptor shape ---

def test_append_stateroom_picker_shape():
    """_append_stateroom_picker builds correct descriptor for denali_explorer."""
    session = make_session()
    cr = create_draft(session, {"cruise_id": "denali_explorer"})
    draft_id = cr["draft_id"]
    set_fare(session, {"draft_id": draft_id, "package": "good_to_go"})

    components: list = []
    _append_stateroom_picker(components, {"draft_id": draft_id}, session)

    assert len(components) == 1
    picker = components[0]
    assert picker["type"] == "stateroom_picker"
    assert picker["draft_id"] == draft_id
    assert isinstance(picker["categories"], list)
    assert len(picker["categories"]) == 4
    assert picker["locations"] == ["Forward", "Midship", "Aft"]


def test_stateroom_picker_categories_have_delta_formatted():
    """stateroom_picker categories have delta_formatted field."""
    session = make_session()
    cr = create_draft(session, {"cruise_id": "denali_explorer"})
    draft_id = cr["draft_id"]

    components: list = []
    _append_stateroom_picker(components, {"draft_id": draft_id}, session)

    picker = components[0]
    for cat in picker["categories"]:
        assert "delta_formatted" in cat, f"category {cat} missing delta_formatted"


def test_stateroom_picker_scarcity_only_when_field_present():
    """Scarcity chip present for Verandah (remaining_at_fare=3) but not for Inside (null)."""
    session = make_session()
    cr = create_draft(session, {"cruise_id": "denali_explorer"})
    draft_id = cr["draft_id"]

    components: list = []
    _append_stateroom_picker(components, {"draft_id": draft_id}, session)

    picker = components[0]
    by_cat = {c["category"]: c for c in picker["categories"]}

    # Verandah has remaining_at_fare=3 in denali_explorer → scarcity present
    assert "Verandah" in by_cat
    verandah = by_cat["Verandah"]
    assert "scarcity" in verandah, f"Verandah should have scarcity, got {verandah}"
    assert any("3 left" in s for s in verandah["scarcity"]), f"Expected '3 left' signal in {verandah['scarcity']}"

    # Inside has remaining_at_fare=null → no scarcity
    assert "Inside" in by_cat
    inside = by_cat["Inside"]
    assert "scarcity" not in inside, f"Inside should NOT have scarcity, got {inside}"


def test_stateroom_picker_total_formatted_present():
    """stateroom_picker includes total_formatted from draft."""
    session = make_session()
    cr = create_draft(session, {"cruise_id": "denali_explorer"})
    draft_id = cr["draft_id"]

    components: list = []
    _append_stateroom_picker(components, {"draft_id": draft_id}, session)

    picker = components[0]
    assert picker.get("total_formatted") is not None


def test_append_stateroom_picker_no_draft_id_does_nothing():
    """_append_stateroom_picker with no draft_id does not append."""
    components: list = []
    _append_stateroom_picker(components, {}, make_session())
    assert components == []
