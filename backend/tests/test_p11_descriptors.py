"""
P11 descriptor builder tests.

Tests:
- dining_tiles descriptor: grid marks sold_out where capacity 0; reserved marking
- land_builder descriptor: options carry conflict reason; selected state
- action chaining: set_stateroom → dining_tiles; reserve_dining → refreshed dining_tiles; set_land_days → land_builder
"""
from __future__ import annotations
import pytest
from app.models import Session
from app.catalog.loader import load_catalog
from app.tools.draft import create_draft, set_fare, set_stateroom
from app.tools.dining import list_dining, reserve_dining
from app.tools.land import list_land_options, set_land_days
from app.routes.action import _append_dining_tiles, _append_land_builder


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_denali_draft(catalog):
    session = Session(session_id="test_p11_denali")
    create_draft(session, {"cruise_id": "denali_explorer"})
    set_fare(session, {"draft_id": session.drafts[0].draft_id, "package": "have_it_all"})
    set_stateroom(session, {"draft_id": session.drafts[0].draft_id, "category": "Verandah", "location": "Midship"})
    return session, session.drafts[0]


# ── Dining descriptor tests ──────────────────────────────────────────────────

def test_dining_tiles_descriptor_has_venues(catalog):
    session, draft = make_denali_draft(catalog)
    components = []
    _append_dining_tiles(components, draft.draft_id, session)
    assert len(components) == 1
    desc = components[0]
    assert desc["type"] == "dining_tiles"
    assert desc["draft_id"] == draft.draft_id
    assert len(desc["venues"]) > 0


def test_dining_tiles_sold_out_marked(catalog):
    """Nights with capacity 0 in catalog must appear as sold_out in the descriptor."""
    session, draft = make_denali_draft(catalog)
    components = []
    _append_dining_tiles(components, draft.draft_id, session)
    venues = components[0]["venues"]
    # Saffron night 3 has capacity 0 in catalog
    saffron = next((v for v in venues if v["venue_id"] == "saffron"), None)
    assert saffron is not None
    night3 = next((n for n in saffron["nights"] if n["night"] == 3), None)
    assert night3 is not None
    assert night3["status"] == "sold_out"


def test_dining_tiles_reserved_night_marked(catalog):
    """After reserving a night, the refreshed descriptor shows that night as 'reserved'."""
    session, draft = make_denali_draft(catalog)
    reserve_dining(session, {"draft_id": draft.draft_id, "venue_id": "saffron", "night": 5})
    components = []
    _append_dining_tiles(components, draft.draft_id, session)
    venues = components[0]["venues"]
    saffron = next(v for v in venues if v["venue_id"] == "saffron")
    night5 = next(n for n in saffron["nights"] if n["night"] == 5)
    assert night5["status"] == "reserved"


def test_dining_tiles_available_night(catalog):
    """An unreserved, non-zero-capacity night should be 'available'."""
    session, draft = make_denali_draft(catalog)
    components = []
    _append_dining_tiles(components, draft.draft_id, session)
    venues = components[0]["venues"]
    saffron = next(v for v in venues if v["venue_id"] == "saffron")
    night9 = next((n for n in saffron["nights"] if n["night"] == 9), None)
    if night9:
        assert night9["status"] == "available"


# ── Land descriptor tests ────────────────────────────────────────────────────

def test_land_builder_descriptor_structure(catalog):
    session, draft = make_denali_draft(catalog)
    components = []
    _append_land_builder(components, draft.draft_id, session)
    assert len(components) == 1
    desc = components[0]
    assert desc["type"] == "land_builder"
    assert desc["draft_id"] == draft.draft_id
    assert len(desc["days"]) > 0
    assert "plan" in desc


def test_land_builder_conflict_reason_present(catalog):
    """Options with conflicts_with should carry conflict_reason."""
    session, draft = make_denali_draft(catalog)
    components = []
    _append_land_builder(components, draft.draft_id, session)
    days = components[0]["days"]
    # Day 2 has domed_rail_d2 and motorcoach_d2 which conflict
    day2 = next((d for d in days if d["day"] == 2), None)
    assert day2 is not None
    opts = day2["options"]
    domed = next((o for o in opts if o["id"] == "domed_rail_d2"), None)
    assert domed is not None
    assert len(domed["conflicts_with"]) > 0
    assert domed["conflict_reason"]  # non-empty string


def test_land_builder_selected_state(catalog):
    """After set_land_days, descriptor shows selected options."""
    session, draft = make_denali_draft(catalog)
    set_land_days(session, {
        "draft_id": draft.draft_id,
        "option_ids": ["coastal_d1", "domed_rail_d2"],
    })
    components = []
    _append_land_builder(components, draft.draft_id, session)
    days = components[0]["days"]
    day1 = next(d for d in days if d["day"] == 1)
    coastal = next(o for o in day1["options"] if o["id"] == "coastal_d1")
    assert coastal["selected"] is True
    # Plan should list selected options
    plan = components[0]["plan"]
    assert any(p["option_id"] == "coastal_d1" for p in plan)
    assert any(p["option_id"] == "domed_rail_d2" for p in plan)


def test_land_builder_non_cruisetour_returns_nothing(catalog):
    """For non-cruisetour cruise, _append_land_builder appends nothing."""
    session = Session(session_id="test_p11_noncruise")
    create_draft(session, {"cruise_id": "glacier_discovery"})
    draft = session.drafts[0]
    set_fare(session, {"draft_id": draft.draft_id, "package": "good_to_go"})
    set_stateroom(session, {"draft_id": draft.draft_id, "category": "Interior", "location": "Midship"})
    components = []
    _append_land_builder(components, draft.draft_id, session)
    assert len(components) == 0
