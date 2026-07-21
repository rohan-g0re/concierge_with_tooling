"""
Unit 0 — search_cruises key fix tests.

Tests:
  1. POST /action/search_cruises with {region: "alaska"} returns a card_row
     component with non-empty cards, length <= 5.
  2. PARITY: build one result via the real search_cruises tool, pass it through
     both action._build_components and gemini_client._map_tool_result_to_component
     — both must yield non-empty cards that agree.
  3. EDGE: a region with zero matches (e.g. "antarctica") returns a card_row
     (possibly empty cards), no crash.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fake Gemini client stubs (same pattern as test_action_parity.py)
# ---------------------------------------------------------------------------

class FakePart:
    def __init__(self, *, text=None, function_call=None):
        self.text = text
        self.function_call = function_call


class FakeContent:
    def __init__(self, role: str, parts: list):
        self.role = role
        self.parts = parts


class FakeCandidate:
    def __init__(self, parts: list):
        self.content = FakeContent(role="model", parts=parts)


class FakeResponse:
    def __init__(self, candidates):
        self.candidates = candidates


class FakeStreamChunk:
    def __init__(self, text: str):
        self.candidates = [FakeCandidate([FakePart(text=text)])]


class FakeTypes:
    class FunctionDeclaration:
        def __init__(self, name, description="", parameters=None):
            self.name = name

    class Tool:
        def __init__(self, function_declarations=None):
            self.function_declarations = function_declarations or []

    class GenerateContentConfig:
        def __init__(self, tools=None, system_instruction=None):
            self.tools = tools or []

    class Content:
        def __init__(self, role="user", parts=None):
            self.role = role
            self.parts = parts or []

    class Part:
        def __init__(self, text=None, function_call=None):
            self.text = text
            self.function_call = function_call

        @staticmethod
        def from_function_response(name: str, response: dict):
            p = FakeTypes.Part()
            p._fn_response = (name, response)
            return p


@pytest.fixture(autouse=True)
def patch_genai(monkeypatch):
    """Patch google.genai so gemini_client never touches the real SDK."""
    import sys
    fake_genai_module = MagicMock()
    fake_types_module = FakeTypes()
    fake_google = MagicMock()
    fake_google.genai = fake_genai_module
    sys.modules.setdefault("google", fake_google)
    sys.modules["google.genai"] = fake_genai_module
    sys.modules["google.genai.types"] = fake_types_module
    yield fake_genai_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_client():
    """Return a fresh TestClient."""
    from app.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: POST /action/search_cruises → card_row with non-empty cards, len <= 5
# ---------------------------------------------------------------------------

def test_search_cruises_action_returns_card_row():
    """
    POST /action/search_cruises with region=alaska must return a card_row
    component whose cards list is non-empty and has length <= 5.
    """
    client = make_client()
    session_id = "test-search-fix-t1"

    resp = client.post(
        "/action/search_cruises",
        json={"session_id": session_id, "args": {"region": "alaska"}},
    )
    assert resp.status_code == 200, f"Unexpected status: {resp.status_code} {resp.text}"
    data = resp.json()

    # Must not be a top-level error
    assert "error" not in data, f"Unexpected error in response: {data}"

    components = data.get("components", [])
    assert components, "components must not be empty"

    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is not None, f"No card_row component found in: {components}"

    cards = card_row.get("cards", [])
    assert len(cards) > 0, "cards must be non-empty for alaska region"
    assert len(cards) <= 5, f"cards must be at most 5, got {len(cards)}"


# ---------------------------------------------------------------------------
# Test 2: Parity — _build_components and _map_tool_result_to_component agree
# ---------------------------------------------------------------------------

def test_parity_build_components_vs_map_tool_result():
    """
    Build a raw result from the real search_cruises tool, then pass it through
    both:
      - action._build_components("search_cruises", result, session)
      - gemini_client._map_tool_result_to_component("search_cruises", result)

    Both must produce a card_row with the same non-empty cards list.
    """
    from app.routes.action import _build_components
    from app.llm.gemini_client import _map_tool_result_to_component
    from app.tools.search import search_cruises
    from app.models import Session

    session = Session(session_id="test-search-fix-t2")
    args = {"region": "alaska"}
    result = search_cruises(session, args)

    # Verify the raw result has "results" key (not "cruises")
    assert "results" in result, f"search_cruises must return 'results' key, got keys: {list(result.keys())}"
    assert len(result["results"]) > 0, "Expected at least one alaska cruise in catalog"

    # action path
    action_components = _build_components("search_cruises", result, session)
    action_card_row = next((c for c in action_components if c.get("type") == "card_row"), None)
    assert action_card_row is not None, f"_build_components produced no card_row: {action_components}"
    action_cards = action_card_row.get("cards", [])
    assert len(action_cards) > 0, "_build_components returned empty cards"
    assert len(action_cards) <= 5, f"_build_components returned more than 5 cards: {len(action_cards)}"

    # gemini_client path
    gc_component = _map_tool_result_to_component("search_cruises", result)
    assert gc_component is not None, "_map_tool_result_to_component returned None"
    assert gc_component.get("type") == "card_row", f"Expected card_row, got: {gc_component}"
    gc_cards = gc_component.get("cards", [])
    assert len(gc_cards) > 0, "_map_tool_result_to_component returned empty cards"
    assert len(gc_cards) <= 5, f"_map_tool_result_to_component returned more than 5 cards: {len(gc_cards)}"

    # Both paths must agree on cards
    assert action_cards == gc_cards, (
        f"Parity failure: action cards != gemini_client cards.\n"
        f"action: {action_cards}\ngc: {gc_cards}"
    )


# ---------------------------------------------------------------------------
# Test 3: Edge — zero-match region returns card_row without crashing
# ---------------------------------------------------------------------------

def test_search_cruises_zero_matches_no_crash():
    """
    POST /action/search_cruises with a region that has no catalog entries
    (e.g. "antarctica") must return a card_row component (possibly empty cards)
    without raising any exception or returning a top-level error.
    """
    client = make_client()
    session_id = "test-search-fix-t3"

    resp = client.post(
        "/action/search_cruises",
        json={"session_id": session_id, "args": {"region": "antarctica"}},
    )
    assert resp.status_code == 200, f"Unexpected status: {resp.status_code} {resp.text}"
    data = resp.json()

    # Must not be a top-level error
    assert "error" not in data, f"Unexpected error in response: {data}"

    components = data.get("components", [])
    assert components, "components must not be empty even for zero matches"

    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is not None, f"No card_row component for zero-match region: {components}"

    # cards may be empty — just must not crash and must be a list
    cards = card_row.get("cards")
    assert isinstance(cards, list), f"cards must be a list, got: {type(cards)}"
