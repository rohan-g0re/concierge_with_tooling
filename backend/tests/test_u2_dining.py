"""
U2 tests — set_dining_time, reserve_dining dining_confirmation, tool registry,
mapper parity (institutional learning #1 guard).
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.models import Session
from app.catalog.loader import load_catalog
from app.tools.draft import create_draft, set_fare, set_stateroom
from app.tools.dining import list_dining, reserve_dining, set_dining_time


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_session(session_id: str = "test-u2-session", party: int = 2) -> Session:
    return Session(session_id=session_id, party=party)


def make_denali_draft(session: Session) -> str:
    """Create a fully-configured denali_explorer draft and return draft_id."""
    result = create_draft(session, {"cruise_id": "denali_explorer"})
    assert "error" not in result, f"create_draft failed: {result}"
    draft_id = result["draft_id"]
    set_fare(session, {"draft_id": draft_id, "package": "have_it_all"})
    set_stateroom(session, {"draft_id": draft_id, "category": "Verandah", "location": "Midship"})
    return draft_id


# ---------------------------------------------------------------------------
# U2 Test 1: set_dining_time stores preference on draft
# ---------------------------------------------------------------------------

def test_set_dining_time_stores_pref(catalog):
    """set_dining_time stores time_slot on draft.dining_time_pref."""
    session = make_session("test-u2-t1")
    draft_id = make_denali_draft(session)

    result = set_dining_time(session, {"draft_id": draft_id, "time_slot": "early"})
    assert "error" not in result, f"set_dining_time failed: {result}"
    assert result["time_slot"] == "early"
    assert result["time_label"] == "5:30 PM"
    assert result["draft_id"] == draft_id

    # Verify preference stored on draft
    draft = next(d for d in session.drafts if d.draft_id == draft_id)
    assert draft.dining_time_pref == "early", f"Expected 'early', got {draft.dining_time_pref!r}"


def test_set_dining_time_all_slots(catalog):
    """set_dining_time accepts all three valid time slots."""
    _TIME_LABELS = {"early": "5:30 PM", "main": "7:30 PM", "late": "9:00 PM"}
    for slot, label in _TIME_LABELS.items():
        session = make_session(f"test-u2-t1-{slot}")
        draft_id = make_denali_draft(session)
        result = set_dining_time(session, {"draft_id": draft_id, "time_slot": slot})
        assert "error" not in result, f"set_dining_time({slot!r}) failed: {result}"
        assert result["time_label"] == label


def test_set_dining_time_overwrites_pref(catalog):
    """set_dining_time called twice overwrites previous preference."""
    session = make_session("test-u2-t1-overwrite")
    draft_id = make_denali_draft(session)

    set_dining_time(session, {"draft_id": draft_id, "time_slot": "early"})
    result = set_dining_time(session, {"draft_id": draft_id, "time_slot": "late"})
    assert "error" not in result
    assert result["time_slot"] == "late"
    draft = next(d for d in session.drafts if d.draft_id == draft_id)
    assert draft.dining_time_pref == "late"


# ---------------------------------------------------------------------------
# U2 Test 2: set_dining_time rejects bad draft_id
# ---------------------------------------------------------------------------

def test_set_dining_time_bad_draft_id(catalog):
    """set_dining_time returns draft_not_found for unknown draft_id."""
    session = make_session("test-u2-t2")
    result = set_dining_time(session, {"draft_id": "nonexistent-draft", "time_slot": "main"})
    assert result.get("error") == "draft_not_found", f"Expected draft_not_found, got: {result}"
    assert "message" in result


def test_set_dining_time_invalid_slot(catalog):
    """set_dining_time rejects unknown time_slot."""
    session = make_session("test-u2-t2-slot")
    draft_id = make_denali_draft(session)
    result = set_dining_time(session, {"draft_id": draft_id, "time_slot": "midnight"})
    assert result.get("error") == "invalid_time_slot", f"Expected invalid_time_slot, got: {result}"


# ---------------------------------------------------------------------------
# U2 Test 3: reserve_dining result shape — confirmation fields present
# ---------------------------------------------------------------------------

def test_reserve_dining_result_has_confirmation_fields(catalog):
    """reserve_dining result includes venue_id, night, draft_id for dining_confirmation."""
    session = make_session("test-u2-t3")
    draft_id = make_denali_draft(session)

    result = reserve_dining(session, {"draft_id": draft_id, "venue_id": "saffron", "night": 5})
    assert "error" not in result, f"reserve_dining failed: {result}"
    assert result.get("venue_id") == "saffron"
    assert result.get("night") == 5
    assert result.get("draft_id") == draft_id


# ---------------------------------------------------------------------------
# U2 Test 4: set_dining_time in TOOL_REGISTRY
# ---------------------------------------------------------------------------

def test_set_dining_time_in_tool_registry():
    """set_dining_time is registered in TOOL_REGISTRY."""
    from app.tools import TOOL_REGISTRY
    assert "set_dining_time" in TOOL_REGISTRY, (
        f"set_dining_time not in TOOL_REGISTRY. Keys: {sorted(TOOL_REGISTRY)}"
    )
    handler, schema = TOOL_REGISTRY["set_dining_time"]
    assert callable(handler)
    required = schema["parameters"].get("required", [])
    assert "draft_id" in required
    assert "time_slot" in required


def test_set_dining_time_not_in_gemini_declarations():
    """set_dining_time must NOT appear in Gemini FunctionDeclarations (action-only)."""
    from app.llm.gemini_client import _ACTION_ONLY_TOOLS
    assert "set_dining_time" in _ACTION_ONLY_TOOLS, (
        "set_dining_time must be in _ACTION_ONLY_TOOLS to be excluded from Gemini declarations"
    )


# ---------------------------------------------------------------------------
# U2 Test 5: Mapper parity — dining_confirmation and dining_time_receipt
# ---------------------------------------------------------------------------

def test_mappers_parity_reserve_dining(catalog):
    """
    reserve_dining result maps to dining_confirmation in BOTH:
      - gemini_client._map_tool_result_to_component
      - action._build_components
    Institutional learning #1 guard.
    """
    from app.llm.gemini_client import _map_tool_result_to_component
    from app.routes.action import _build_components

    session = make_session("test-u2-t5-reserve")
    draft_id = make_denali_draft(session)
    result = reserve_dining(session, {"draft_id": draft_id, "venue_id": "saffron", "night": 5})
    assert "error" not in result, f"reserve_dining failed: {result}"

    # Gemini mapper
    gemini_comp = _map_tool_result_to_component("reserve_dining", result)
    assert gemini_comp is not None, "_map_tool_result_to_component returned None for reserve_dining"
    assert gemini_comp["type"] == "dining_confirmation", (
        f"Expected type='dining_confirmation', got: {gemini_comp}"
    )
    assert gemini_comp.get("venue_id") == "saffron"
    assert gemini_comp.get("night") == 5

    # Action mapper
    action_comps = _build_components("reserve_dining", result, session)
    confirmation_comps = [c for c in action_comps if c.get("type") == "dining_confirmation"]
    assert len(confirmation_comps) == 1, (
        f"Expected exactly 1 dining_confirmation from _build_components, got: {action_comps}"
    )
    action_comp = confirmation_comps[0]
    assert action_comp.get("venue_id") == "saffron"
    assert action_comp.get("night") == 5

    # Parity: both produce same venue_id and night
    assert gemini_comp.get("venue_id") == action_comp.get("venue_id"), "venue_id parity failure"
    assert gemini_comp.get("night") == action_comp.get("night"), "night parity failure"


def test_mappers_parity_set_dining_time(catalog):
    """
    set_dining_time result maps to dining_time_receipt in BOTH mappers.
    Institutional learning #1 guard.
    """
    from app.llm.gemini_client import _map_tool_result_to_component
    from app.routes.action import _build_components

    session = make_session("test-u2-t5-time")
    draft_id = make_denali_draft(session)
    result = set_dining_time(session, {"draft_id": draft_id, "time_slot": "main"})
    assert "error" not in result, f"set_dining_time failed: {result}"

    # Gemini mapper
    gemini_comp = _map_tool_result_to_component("set_dining_time", result)
    assert gemini_comp is not None, "_map_tool_result_to_component returned None for set_dining_time"
    assert gemini_comp["type"] == "dining_time_receipt", (
        f"Expected type='dining_time_receipt', got: {gemini_comp}"
    )
    assert gemini_comp.get("time_slot") == "main"
    assert gemini_comp.get("time_label") == "7:30 PM"

    # Action mapper
    action_comps = _build_components("set_dining_time", result, session)
    receipt_comps = [c for c in action_comps if c.get("type") == "dining_time_receipt"]
    assert len(receipt_comps) == 1, (
        f"Expected exactly 1 dining_time_receipt from _build_components, got: {action_comps}"
    )
    action_comp = receipt_comps[0]
    assert action_comp.get("time_slot") == "main"
    assert action_comp.get("time_label") == "7:30 PM"

    # Parity
    assert gemini_comp.get("time_slot") == action_comp.get("time_slot"), "time_slot parity failure"
    assert gemini_comp.get("time_label") == action_comp.get("time_label"), "time_label parity failure"


def test_reserve_dining_no_longer_re_emits_dining_tiles(catalog):
    """
    After reserve_dining, _build_components must NOT emit a dining_tiles descriptor.
    (Bug 3 fix — no more silent identical-panel re-emit.)
    """
    from app.routes.action import _build_components

    session = make_session("test-u2-t5-notiles")
    draft_id = make_denali_draft(session)
    result = reserve_dining(session, {"draft_id": draft_id, "venue_id": "saffron", "night": 5})
    assert "error" not in result

    components = _build_components("reserve_dining", result, session)
    tile_comps = [c for c in components if c.get("type") == "dining_tiles"]
    assert len(tile_comps) == 0, (
        f"reserve_dining must not re-emit dining_tiles — found: {tile_comps}"
    )
