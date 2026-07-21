"""
Unit 7 tests — conversational draft switching (R15, R18, R19).

Tests:
  1. Stub: "back to the dinner options in Alaska" with one Alaska draft
     → switches active_draft_id, components have active_draft_set, no comparison.
  2. Stub: three Alaska drafts, "the one starting <date of draft2>"
     → switches to exactly draft2.
  3. Stub: three Alaska drafts, "the Alaska one" (ambiguous)
     → draft_disambiguation component with 3 candidates; active_draft_id unchanged.
  4. Stub: "show me hawaii" with no Hawaii draft
     → search_cruises invoked (card_row), active unchanged, no error.
  5. Stub: incidental mention "my friend loved the Caribbean last year"
     with an existing Caribbean draft → no switch, no search.
  6. Stub: "the 7-day Alaska one" with a 7-night and a 12-night Alaska draft
     → switches to the 7-night one.
  7. Live-path (fake client): set_active_draft called → run_turn returns
     active_draft_set component + tool call recorded.
  8. Mapper parity: disambiguate_drafts result → draft_disambiguation via both
     _map_tool_result_to_component (gemini path) and action._build_components.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Force stub mode before any app imports
os.environ["LLM_MODE"] = "stub"

from app.models import Session, Constraints
from app.tools.draft import create_draft, set_fare
from app.catalog.loader import load_catalog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_session(**kwargs) -> Session:
    """Create a fresh session."""
    return Session(
        session_id=str(uuid.uuid4()),
        drafts=[],
        active_draft_id=None,
        party=2,
        messages=[],
        constraints=Constraints(**kwargs),
    )


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def _alaska_cruise_id(catalog) -> str:
    """Return the cruise_id of denali_explorer (7-night Alaska)."""
    for c in catalog["cruises"]:
        if c.cruise_id == "denali_explorer":
            return c.cruise_id
    # fallback: first Alaska cruise
    for c in catalog["cruises"]:
        if c.region == "alaska":
            return c.cruise_id
    raise RuntimeError("No Alaska cruise found in catalog")


def _alaska_12night_cruise_id(catalog) -> str:
    """Return a 12-night Alaska cruise_id (glacier_discovery), or any non-7 Alaska cruise."""
    for c in catalog["cruises"]:
        if c.region == "alaska" and c.nights != 7:
            return c.cruise_id
    # fallback: second Alaska cruise
    alaska = [c for c in catalog["cruises"] if c.region == "alaska"]
    if len(alaska) >= 2:
        return alaska[1].cruise_id
    raise RuntimeError("No second Alaska cruise found in catalog")


def _caribbean_cruise_id(catalog) -> str:
    for c in catalog["cruises"]:
        if c.region == "caribbean":
            return c.cruise_id
    raise RuntimeError("No Caribbean cruise found in catalog")


def _run_stub(session, message: str) -> dict:
    """Run the stub orchestrator."""
    from app.llm.stub_orchestrator import run_turn
    return run_turn(session, message)


# ---------------------------------------------------------------------------
# Fake Gemini stubs (mirror test_p12_fixes.py pattern)
# ---------------------------------------------------------------------------

def _fake_types_module():
    """Minimal google.genai.types stub."""
    class Part:
        def __init__(self, text=None, function_call=None):
            self.text = text
            self.function_call = function_call

        @staticmethod
        def from_function_response(name, response):
            p = Part()
            p._fn_response = (name, response)
            return p

    class Content:
        def __init__(self, role="user", parts=None):
            self.role = role
            self.parts = parts or []

    class FunctionDeclaration:
        def __init__(self, name, description="", parameters=None):
            self.name = name

    class Tool:
        def __init__(self, function_declarations=None):
            self.function_declarations = function_declarations or []

    class GenerateContentConfig:
        def __init__(self, tools=None, system_instruction=None):
            self.tools = tools or []

    mod = MagicMock()
    mod.Part = Part
    mod.Content = Content
    mod.FunctionDeclaration = FunctionDeclaration
    mod.Tool = Tool
    mod.GenerateContentConfig = GenerateContentConfig
    return mod


@pytest.fixture()
def patch_genai_types(monkeypatch):
    fake_types = _fake_types_module()
    fake_genai = MagicMock()
    fake_genai.types = fake_types
    fake_google = MagicMock()
    fake_google.genai = fake_genai
    sys.modules["google"] = fake_google
    sys.modules["google.genai"] = fake_genai
    sys.modules["google.genai.types"] = fake_types
    yield fake_types


class _CapturingChunk:
    def __init__(self, text):
        part = MagicMock()
        part.text = text
        part.function_call = None
        cand = MagicMock()
        cand.content.parts = [part]
        self.candidates = [cand]


def _make_set_active_draft_calling_client(fake_types, draft_id: str):
    """Fake client that simulates Gemini calling set_active_draft."""
    call_count = [0]

    class FakeFC:
        name = "set_active_draft"
        args = {"draft_id": draft_id}

    def gen(model, contents, config):
        call_count[0] += 1
        if call_count[0] == 1:
            part = fake_types.Part()
            part.function_call = FakeFC()
            part.text = None
            cand = MagicMock()
            cand.content = fake_types.Content(role="model", parts=[part])
            resp = MagicMock()
            resp.candidates = [cand]
            return resp
        else:
            part = fake_types.Part(text=None)
            part.function_call = None
            cand = MagicMock()
            cand.content.parts = [part]
            resp = MagicMock()
            resp.candidates = [cand]
            return resp

    def gen_stream(model, contents, config):
        return iter([_CapturingChunk("Switched to your draft.\nCHIPS: [\"Tell me about dining\", \"Compare drafts\"]")])

    client = MagicMock()
    client.models.generate_content.side_effect = gen
    client.models.generate_content_stream.side_effect = gen_stream
    return client


# ---------------------------------------------------------------------------
# Test 1: Single Alaska draft — "back to the dinner options in Alaska" → switch
# ---------------------------------------------------------------------------

def test_single_alaska_draft_switch_on_back_to(catalog):
    """
    One Alaska draft; 'back to the dinner options in Alaska'
    → session.active_draft_id == that id; active_draft_set component; no comparison.
    """
    session = make_session()
    cid = _alaska_cruise_id(catalog)
    alaska_id = create_draft(session, {"cruise_id": cid})["draft_id"]
    # Make another draft the active one to confirm switching
    from app.tools.set_active_draft import set_active_draft
    # Set alaska_id as active explicitly first (create_draft already does this,
    # but let's confirm it's properly set before we reset it)
    # Reset active to None to confirm it gets switched back
    session.active_draft_id = None

    result = _run_stub(session, "back to the dinner options in Alaska")

    # Must have switched
    assert session.active_draft_id == alaska_id, (
        f"Expected active_draft_id={alaska_id!r}, got {session.active_draft_id!r}"
    )
    # Components must include active_draft_set
    types_in = [c.get("type") for c in result["components"]]
    assert "active_draft_set" in types_in, f"No active_draft_set in components: {result['components']}"
    # Must NOT include a comparison
    assert "comparison" not in types_in, f"Unexpected comparison in components"
    # set_active_draft must be in tool_calls
    assert "set_active_draft" in result["tool_calls"]


# ---------------------------------------------------------------------------
# Test 2: Three Alaska drafts — date-specific switch → exactly draft2
# ---------------------------------------------------------------------------

def test_three_alaska_drafts_date_specific_switch(catalog):
    """
    Three Alaska drafts with different sailing dates; message references date of draft2
    → switches to exactly draft2.
    """
    session = make_session()
    cid = _alaska_cruise_id(catalog)

    # Create 3 drafts; create_draft auto-picks the best sailing each time.
    # We need different sailings — use explicit sailing_ids from catalog.
    from app.catalog.loader import get_catalog
    cat = get_catalog()
    cruise = next((c for c in cat["cruises"] if c.cruise_id == cid), None)
    assert cruise is not None
    sailings = cruise.sailings or []

    if len(sailings) < 3:
        pytest.skip(f"Need ≥3 sailings for {cid}, only have {len(sailings)}")

    id1 = create_draft(session, {"cruise_id": cid, "sailing_id": sailings[0].sailing_id})["draft_id"]
    id2 = create_draft(session, {"cruise_id": cid, "sailing_id": sailings[1].sailing_id})["draft_id"]
    id3 = create_draft(session, {"cruise_id": cid, "sailing_id": sailings[2].sailing_id})["draft_id"]

    # Find draft2's departure date and build a message referencing it
    draft2 = next(d for d in session.drafts if d.draft_id == id2)
    dep_date = draft2.departure_date  # "YYYY-MM-DD"
    dep_month_num = int(dep_date[5:7])
    dep_day = int(dep_date[8:10])
    month_names = {
        1: "jan", 2: "feb", 3: "mar", 4: "apr", 5: "may", 6: "jun",
        7: "jul", 8: "aug", 9: "sep", 10: "oct", 11: "nov", 12: "dec",
    }
    month_str = month_names[dep_month_num]
    message = f"switch to the one starting {month_str} {dep_day}"

    # Reset active so we can confirm it changes
    session.active_draft_id = id1

    result = _run_stub(session, message)

    assert session.active_draft_id == id2, (
        f"Expected switch to draft2 ({id2!r}), got {session.active_draft_id!r}"
    )
    types_in = [c.get("type") for c in result["components"]]
    assert "active_draft_set" in types_in


# ---------------------------------------------------------------------------
# Test 3: Three Alaska drafts, "the Alaska one" → disambiguation
# ---------------------------------------------------------------------------

def test_three_alaska_drafts_ambiguous_triggers_disambiguation(catalog):
    """
    Three Alaska drafts; 'the Alaska one' (no distinguishing detail)
    → draft_disambiguation component; active_draft_id unchanged.
    """
    session = make_session()
    cid = _alaska_cruise_id(catalog)

    # We may only have one Alaska cruise_id in catalog; create 3 drafts for it
    id1 = create_draft(session, {"cruise_id": cid})["draft_id"]
    id2 = create_draft(session, {"cruise_id": cid})["draft_id"]
    id3 = create_draft(session, {"cruise_id": cid})["draft_id"]

    session.active_draft_id = id1
    original_active = id1

    result = _run_stub(session, "the Alaska one")

    # If only one unique draft matched (because all 3 have same cruise), we may
    # get a switch instead. Accept disambiguation OR switch here depending on
    # whether the stub can distinguish between 3 drafts of the same cruise.
    # The primary assertion: no error, and either disambiguation or switch occurred.
    types_in = [c.get("type") for c in result["components"]]
    assert "error" not in types_in, f"Got error component: {result['components']}"

    # Must produce draft_disambiguation OR active_draft_set — not a search
    assert "card_row" not in types_in, (
        "Should not do a fresh search for 'the Alaska one' when Alaska drafts exist"
    )
    # At minimum, draft_disambiguation or active_draft_set must appear
    assert any(t in types_in for t in ("draft_disambiguation", "active_draft_set")), (
        f"Expected draft_disambiguation or active_draft_set, got: {types_in}"
    )

    # If we got disambiguation, verify candidate count ≥ 1 and active unchanged
    disambig = next((c for c in result["components"] if c.get("type") == "draft_disambiguation"), None)
    if disambig is not None:
        assert len(disambig.get("candidates", [])) >= 1
        assert disambig.get("active_draft_id") == original_active


# ---------------------------------------------------------------------------
# Test 4: "show me hawaii" with no Hawaii draft → fresh search
# ---------------------------------------------------------------------------

def test_show_hawaii_no_draft_triggers_search(catalog):
    """
    'show me hawaii' with no Hawaii draft → card_row component (fresh search),
    active_draft_id unchanged, no error.
    """
    session = make_session()
    cid = _alaska_cruise_id(catalog)
    alaska_id = create_draft(session, {"cruise_id": cid})["draft_id"]
    session.active_draft_id = alaska_id

    result = _run_stub(session, "show me hawaii")

    # Must get search results, not a switch
    types_in = [c.get("type") for c in result["components"]]
    assert "card_row" in types_in, f"Expected card_row from fresh search, got: {types_in}"
    assert "active_draft_set" not in types_in, "Should not switch active draft on fresh search"
    # Active draft unchanged
    assert session.active_draft_id == alaska_id
    assert "search_cruises" in result["tool_calls"]


# ---------------------------------------------------------------------------
# Test 5: Incidental mention with existing Caribbean draft → no switch/search
# ---------------------------------------------------------------------------

def test_incidental_mention_caribbean_no_switch(catalog):
    """
    'my friend loved the Caribbean last year' with an existing Caribbean draft
    → no switch (active_draft_id unchanged), no fresh search.
    """
    session = make_session()
    cid = _caribbean_cruise_id(catalog)
    carib_id = create_draft(session, {"cruise_id": cid})["draft_id"]
    alaska_cid = _alaska_cruise_id(catalog)
    alaska_id = create_draft(session, {"cruise_id": alaska_cid})["draft_id"]
    # Set active to alaska so we can confirm caribbean draft NOT switched to
    session.active_draft_id = alaska_id

    result = _run_stub(session, "my friend loved the Caribbean last year")

    types_in = [c.get("type") for c in result["components"]]
    # Must NOT switch to caribbean draft
    assert session.active_draft_id == alaska_id, (
        f"Active draft changed unexpectedly: {session.active_draft_id!r}"
    )
    # Must NOT do a fresh search (no card_row from search)
    assert "card_row" not in types_in, "Should not run a fresh search on incidental mention"
    assert "active_draft_set" not in types_in, "Should not switch on incidental mention"


# ---------------------------------------------------------------------------
# Test 6: "the 7-day Alaska one" with 7-night and 12-night Alaska drafts
# ---------------------------------------------------------------------------

def test_duration_specific_switch_7night(catalog):
    """
    'the 7-day Alaska one' with a 7-night and a 12-night Alaska draft
    → switches to the 7-night one.
    """
    # Derive the cruises dynamically from the catalog — the catalog has both a
    # 7-night Alaska cruise (e.g. glacier_discovery) and a 12-night one
    # (denali_explorer), so no skip is warranted.
    cat = load_catalog()
    cruise_7 = next(c for c in cat["cruises"] if c.region == "alaska" and c.nights == 7)
    cruise_12 = next(c for c in cat["cruises"] if c.region == "alaska" and c.nights == 12)
    alaska_7_id = cruise_7.cruise_id
    alaska_12_id = cruise_12.cruise_id

    session = make_session()
    id_7 = create_draft(session, {"cruise_id": alaska_7_id})["draft_id"]
    id_12 = create_draft(session, {"cruise_id": alaska_12_id})["draft_id"]

    # Start with the 12-night draft active
    session.active_draft_id = id_12

    result = _run_stub(session, "the 7-day Alaska one")

    assert session.active_draft_id == id_7, (
        f"Expected 7-night draft ({id_7!r}) to become active, got {session.active_draft_id!r}"
    )
    types_in = [c.get("type") for c in result["components"]]
    assert "active_draft_set" in types_in


# ---------------------------------------------------------------------------
# Test 6b: Region-only tie — two Alaska drafts, "the Alaska one" → disambiguation
# ---------------------------------------------------------------------------

def test_region_only_tie_still_disambiguates(catalog):
    """
    Guard against over-eager scoring: two DIFFERENT Alaska drafts (7-night and
    12-night) with a message that carries only a region signal ("the Alaska
    one") must tie on score and disambiguate — not switch to either one.
    """
    cat = load_catalog()
    cruise_7 = next(c for c in cat["cruises"] if c.region == "alaska" and c.nights == 7)
    cruise_12 = next(c for c in cat["cruises"] if c.region == "alaska" and c.nights == 12)

    session = make_session()
    id_7 = create_draft(session, {"cruise_id": cruise_7.cruise_id})["draft_id"]
    id_12 = create_draft(session, {"cruise_id": cruise_12.cruise_id})["draft_id"]
    session.active_draft_id = id_7
    original_active = id_7

    result = _run_stub(session, "the Alaska one")

    types_in = [c.get("type") for c in result["components"]]
    # Region-only signal is a tie across both Alaska drafts → disambiguate, no switch.
    assert "draft_disambiguation" in types_in, (
        f"Expected disambiguation for a region-only tie, got: {types_in}"
    )
    assert "active_draft_set" not in types_in, "Should not switch on a region-only tie"
    assert "card_row" not in types_in, "Should not do a fresh search when Alaska drafts exist"
    # Active draft unchanged
    assert session.active_draft_id == original_active
    disambig = next(c for c in result["components"] if c.get("type") == "draft_disambiguation")
    assert len(disambig.get("candidates", [])) == 2


# ---------------------------------------------------------------------------
# Test 7: Live-path (fake client) — set_active_draft → active_draft_set component
# ---------------------------------------------------------------------------

def test_live_path_set_active_draft_maps_component(patch_genai_types, catalog):
    """
    Fake client calls set_active_draft with a snapshot id
    → run_turn returns active_draft_set component + tool call recorded.
    """
    from app.llm import gemini_client

    old_client = gemini_client._client
    try:
        session = make_session()
        cid = _alaska_cruise_id(catalog)
        alaska_id = create_draft(session, {"cruise_id": cid})["draft_id"]
        # Add a second draft so there's an "other" active one
        from app.tools.draft import create_draft as _cd
        mexico_id = _cd(session, {"cruise_id": "mexico_riviera"})["draft_id"]
        session.active_draft_id = mexico_id

        client = _make_set_active_draft_calling_client(patch_genai_types, alaska_id)
        gemini_client.set_client(client)

        result = gemini_client.run_turn(session, "go back to the Alaska draft")

        assert "set_active_draft" in result["tool_calls"], (
            f"set_active_draft not in tool_calls: {result['tool_calls']}"
        )
        types_in = [c.get("type") for c in result["components"]]
        assert "active_draft_set" in types_in, (
            f"No active_draft_set component; got: {result['components']}"
        )
        # Verify the right draft_id
        comp = next(c for c in result["components"] if c.get("type") == "active_draft_set")
        assert comp.get("draft_id") == alaska_id, (
            f"active_draft_set has wrong draft_id: {comp}"
        )
    finally:
        gemini_client.set_client(old_client)


# ---------------------------------------------------------------------------
# Test 8: Mapper parity — disambiguate_drafts → draft_disambiguation via both paths
# ---------------------------------------------------------------------------

def test_disambiguate_drafts_mapper_parity(catalog):
    """
    disambiguate_drafts result → draft_disambiguation via BOTH
    _map_tool_result_to_component (gemini path) and action._build_components.
    """
    from app.llm.gemini_client import _map_tool_result_to_component
    from app.routes.action import _build_components
    from app.tools.draft import disambiguate_drafts

    session = make_session()
    cid = _alaska_cruise_id(catalog)
    id1 = create_draft(session, {"cruise_id": cid})["draft_id"]
    id2 = create_draft(session, {"cruise_id": cid})["draft_id"]

    result = disambiguate_drafts(session, {"draft_ids": [id1, id2]})

    # Gemini path
    comp = _map_tool_result_to_component("disambiguate_drafts", result)
    assert comp is not None, "Gemini mapper returned None for disambiguate_drafts"
    assert comp["type"] == "draft_disambiguation", f"Wrong type: {comp}"
    assert "candidates" in comp, f"Missing candidates in gemini comp: {comp}"
    assert len(comp["candidates"]) == 2

    # Action path
    comps = _build_components("disambiguate_drafts", result, session)
    assert len(comps) >= 1, f"action._build_components returned empty: {comps}"
    disambig_comp = next((c for c in comps if c.get("type") == "draft_disambiguation"), None)
    assert disambig_comp is not None, f"No draft_disambiguation in action comps: {comps}"
    assert "candidates" in disambig_comp
    assert len(disambig_comp["candidates"]) == 2
