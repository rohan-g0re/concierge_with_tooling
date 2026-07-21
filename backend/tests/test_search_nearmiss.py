"""
Unit 4 tests — near-miss sections in search_cruises.

Tests:
  1. 14-night query → sections[0] cards all have nights==14; later sections only non-14 (R8/R9)
  2. 14-night query → later section has expected label text (exact label string)
  3. Impossible constraint (nights_min=20) → no_exact True, sections[0].cards==[], ≥1 later non-empty section (R10)
  4. Determinism: two identical calls → identical labels + ordering
  5. No-constraint search → no sections key (back-compat)
  6. Mapper parity: sections/no_exact survive both mapper paths (gemini_client + action._build_components)
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
from app.tools.search import search_cruises


# ---------------------------------------------------------------------------
# Session helper
# ---------------------------------------------------------------------------

def make_session(**kwargs) -> Session:
    """Create a fresh session with optional constraint overrides."""
    return Session(session_id="nearmiss-test", constraints=Constraints(**kwargs))


# ---------------------------------------------------------------------------
# Test 1: 14-night query — exact section cards all 14 nights; later non-14 (R8/R9)
# ---------------------------------------------------------------------------

def test_14night_exact_section_cards_are_14_nights():
    """
    {nights_min:14, nights_max:14} → sections[0].cards all have nights==14;
    later sections contain only non-14-night cruises.
    R8: exact matches always first, never mixed with alternatives.
    R9: labeled near-miss alternatives beneath exact matches.
    """
    session = make_session()
    result = search_cruises(session, {"nights_min": 14, "nights_max": 14})

    assert "sections" in result, "Expected 'sections' key when date/duration constraint present"
    sections = result["sections"]
    assert len(sections) >= 1, "Expected at least sections[0]"

    exact_section = sections[0]
    assert exact_section["label"] is None, "sections[0] label must be None (exact matches)"

    # All exact-section cards must be 14 nights
    for card in exact_section["cards"]:
        assert card["nights"] == 14, (
            f"Exact section card {card['cruise_id']} has nights={card['nights']}, expected 14"
        )

    # Later sections must NOT contain 14-night cruises
    for sec in sections[1:]:
        assert sec["label"] is not None, f"Near-miss section must have a label, got None"
        for card in sec["cards"]:
            assert card["nights"] != 14, (
                f"Near-miss section card {card['cruise_id']} has nights==14 — "
                "should only be in exact section"
            )


# ---------------------------------------------------------------------------
# Test 2: 14-night query — exact label string
# ---------------------------------------------------------------------------

def test_14night_duration_label_text():
    """
    {nights_min:14, nights_max:14} → a later section exists with label
    'Options outside your 14-night request'.
    """
    session = make_session()
    result = search_cruises(session, {"nights_min": 14, "nights_max": 14})

    assert "sections" in result, "Expected 'sections' key"
    sections = result["sections"]
    labels = [s["label"] for s in sections if s["label"] is not None]

    expected_label = "Options outside your 14-night request"
    assert expected_label in labels, (
        f"Expected label {expected_label!r} in sections; got labels: {labels}"
    )


# ---------------------------------------------------------------------------
# Test 3: Impossible constraint → no_exact True, sections[0].cards==[], ≥1 non-empty later section (R10)
# ---------------------------------------------------------------------------

def test_impossible_nights_no_exact():
    """
    {nights_min:20} — no cruise in catalog is 20 nights.
    no_exact must be True, sections[0].cards must be empty,
    at least one later section must be non-empty.
    R10: zero-match → "no exact matches" + closest relaxed alternatives, never empty.
    """
    session = make_session()
    result = search_cruises(session, {"nights_min": 20})

    assert "no_exact" in result, "Expected 'no_exact' key"
    assert result["no_exact"] is True, f"Expected no_exact=True, got {result['no_exact']}"
    assert result["total_matches"] == 0, f"Expected total_matches=0, got {result['total_matches']}"
    assert result["results"] == [], "Expected results==[] when no exact matches"

    assert "sections" in result, "Expected 'sections' key"
    sections = result["sections"]
    assert len(sections) >= 1, "Expected sections[0]"

    exact_section = sections[0]
    assert exact_section["cards"] == [], (
        f"Expected sections[0].cards==[] for impossible constraint, "
        f"got {len(exact_section['cards'])} cards"
    )

    # At least one later section must be non-empty
    later_non_empty = [s for s in sections[1:] if s["cards"]]
    assert len(later_non_empty) >= 1, (
        "Expected at least 1 non-empty near-miss section for impossible constraint (R10)"
    )


# ---------------------------------------------------------------------------
# Test 4: Determinism — two identical calls → identical labels + ordering (R11)
# ---------------------------------------------------------------------------

def test_deterministic_labels_and_ordering():
    """
    Two identical calls with the same args produce identical section labels
    and card ordering.
    R11: all relaxation deterministic in the tool.
    """
    session_a = make_session()
    session_b = make_session()
    args = {"nights_min": 14, "nights_max": 14}

    result_a = search_cruises(session_a, args)
    result_b = make_session()
    result_b = search_cruises(make_session(), args)

    assert "sections" in result_a and "sections" in result_b

    sections_a = result_a["sections"]
    sections_b = result_b["sections"]

    assert len(sections_a) == len(sections_b), (
        f"Section count mismatch: {len(sections_a)} vs {len(sections_b)}"
    )
    for i, (sa, sb) in enumerate(zip(sections_a, sections_b)):
        assert sa["label"] == sb["label"], (
            f"Section {i} label mismatch: {sa['label']!r} vs {sb['label']!r}"
        )
        ids_a = [c["cruise_id"] for c in sa["cards"]]
        ids_b = [c["cruise_id"] for c in sb["cards"]]
        assert ids_a == ids_b, (
            f"Section {i} card ordering mismatch: {ids_a} vs {ids_b}"
        )


# ---------------------------------------------------------------------------
# Test 5: No constraint search → no sections key (back-compat)
# ---------------------------------------------------------------------------

def test_no_constraint_no_sections_key():
    """
    Plain search with no date/duration constraint must NOT include a 'sections' key.
    Back-compat: existing callers that only look at 'results' must not break.
    """
    session = make_session()
    result = search_cruises(session, {})

    assert "sections" not in result, (
        f"'sections' key must be absent for unconstrained search; got keys: {list(result.keys())}"
    )
    assert "no_exact" not in result, (
        f"'no_exact' key must be absent for unconstrained search; got keys: {list(result.keys())}"
    )
    assert "results" in result
    assert "total_matches" in result


# ---------------------------------------------------------------------------
# Test 6: Mapper parity — sections/no_exact survive both mapper paths
# ---------------------------------------------------------------------------

def test_sections_survive_gemini_mapper():
    """
    A sectioned search result (nights_min=14, nights_max=14) must survive
    _map_tool_result_to_component (Gemini path) with sections intact.
    """
    from app.llm.gemini_client import _map_tool_result_to_component

    session = make_session()
    result = search_cruises(session, {"nights_min": 14, "nights_max": 14})
    assert "sections" in result, "Precondition: search_cruises must return sections"

    component = _map_tool_result_to_component("search_cruises", result)

    assert component is not None
    assert component.get("type") == "card_row"
    assert "sections" in component, (
        f"Gemini mapper dropped 'sections'; component keys: {list(component.keys())}"
    )
    assert "no_exact" in component, (
        f"Gemini mapper dropped 'no_exact'; component keys: {list(component.keys())}"
    )
    assert component["no_exact"] == result["no_exact"]

    # sections[0] in component must match sections[0] in raw result (capped at 5)
    comp_sections = component["sections"]
    raw_sections = result["sections"]
    assert len(comp_sections) == len(raw_sections), (
        f"Mapper changed section count: {len(comp_sections)} vs {len(raw_sections)}"
    )
    assert comp_sections[0]["label"] == raw_sections[0]["label"]
    assert len(comp_sections[0]["cards"]) <= 5


# ---------------------------------------------------------------------------
# Test 7: Stub run_turn "20-day bermuda cruise" → nights_min==20, no_exact True, ≥1 non-empty section
# ---------------------------------------------------------------------------

def test_stub_20day_bermuda_no_exact():
    """
    Stub run_turn with '20-day bermuda cruise' (LLM_MODE=stub) must:
      - call search_cruises with nights_min==20 and region==bermuda_bahamas
      - return no_exact True (no catalog cruise is 20 nights)
      - card_row sections[0].cards==[] and ≥1 non-empty later section
    """
    from app.config import get_settings
    get_settings.cache_clear()

    from app.llm.stub_orchestrator import run_turn

    session = make_session()
    response = run_turn(session, "20-day bermuda cruise")

    # Must have routed to search branch
    assert "search_cruises" in response.get("tool_calls", []), (
        f"Expected search_cruises in tool_calls, got {response.get('tool_calls')}"
    )

    components = response.get("components", [])
    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is not None, f"Expected card_row component, got {components}"

    # nights_min==20 → no_exact must be True
    assert card_row.get("no_exact") is True, (
        f"Expected no_exact=True for 20-night constraint, got {card_row.get('no_exact')}"
    )

    # sections present with empty exact section and ≥1 non-empty near-miss section
    sections = card_row.get("sections", [])
    assert len(sections) >= 1, "Expected at least sections[0] in card_row"
    assert sections[0]["cards"] == [], (
        f"Expected sections[0].cards==[] for impossible 20-night constraint, "
        f"got {len(sections[0]['cards'])} cards"
    )
    later_non_empty = [s for s in sections[1:] if s.get("cards")]
    assert len(later_non_empty) >= 1, (
        "Expected at least 1 non-empty near-miss section for 20-night/bermuda query"
    )

    # Also verify the text signals no-exact path
    text = response.get("text", "")
    assert "no exact" in text.lower() or "closest" in text.lower(), (
        f"Expected no-exact preamble in text, got {text!r}"
    )


def test_sections_survive_action_builder():
    """
    A sectioned search result must survive _build_components (action path)
    with sections intact.
    """
    from app.routes.action import _build_components

    session = make_session()
    result = search_cruises(session, {"nights_min": 14, "nights_max": 14})
    assert "sections" in result, "Precondition: search_cruises must return sections"

    components = _build_components("search_cruises", result, session)

    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is not None, f"Expected card_row in action components, got {components}"
    assert "sections" in card_row, (
        f"Action builder dropped 'sections'; card_row keys: {list(card_row.keys())}"
    )
    assert "no_exact" in card_row, (
        f"Action builder dropped 'no_exact'; card_row keys: {list(card_row.keys())}"
    )
    assert card_row["no_exact"] == result["no_exact"]

    # sections integrity
    comp_sections = card_row["sections"]
    raw_sections = result["sections"]
    assert len(comp_sections) == len(raw_sections)
    assert comp_sections[0]["label"] == raw_sections[0]["label"]
    assert len(comp_sections[0]["cards"]) <= 5
