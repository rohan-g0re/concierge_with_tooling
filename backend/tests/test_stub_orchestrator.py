"""
P7 tests — Stub LLM orchestrator (no API key required).

Tests:
  1. 'Show me Alaska cruises' → card_row with ≤5 cards + 2-3 chips via SSE
  2. Off-scope message → one sentence + redirect chips
  3. Greeting → helpful response + chips
  4. Existing 82 tests not broken (this file just adds new tests)
"""
from __future__ import annotations

import json
import os

# Force stub mode for these tests — must happen before any app imports
os.environ["LLM_MODE"] = "stub"

# Must invalidate lru_cache after setting env var
from backend.app.config import get_settings
get_settings.cache_clear()

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helper: parse SSE stream bytes into events
# ---------------------------------------------------------------------------

def parse_sse(content: bytes) -> list[dict]:
    """Parse raw SSE bytes into list of {event, data} dicts."""
    events = []
    current: dict = {}
    for line in content.decode().split("\n"):
        line = line.rstrip("\r")
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[len("data:"):].strip())
        elif line == "" and current:
            events.append(current)
            current = {}
    return events


# ---------------------------------------------------------------------------
# Fixture: reset lru_cache and ensure stub mode around each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def force_stub_mode():
    os.environ["LLM_MODE"] = "stub"
    get_settings.cache_clear()
    # Ensure no injected Gemini client overrides stub selection
    from backend.app.llm import gemini_client
    saved_client = gemini_client._client
    gemini_client._client = None
    yield
    gemini_client._client = saved_client
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Test 1: Alaska cruise search → card_row ≤5 cards + 2-3 chips via SSE
# ---------------------------------------------------------------------------

def test_alaska_cruise_search_returns_card_row():
    """
    'Show me Alaska cruises' must yield SSE with a terminal components event
    containing a card_row component with ≤5 cards and 2-3 chips.
    """
    from backend.app.main import app

    client = TestClient(app)
    resp = client.post("/chat", json={"session_id": "stub-test-1", "message": "Show me Alaska cruises"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = parse_sse(resp.content)
    assert len(events) >= 2, f"Expected ≥2 SSE events, got {events}"

    # Last event must be components
    last = events[-1]
    assert last["event"] == "components", f"Last event must be 'components', got {last}"

    components = last["data"]["components"]
    chips = last["data"]["chips"]

    # Find card_row component
    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is not None, f"Expected card_row component, got {components}"
    assert len(card_row["cards"]) >= 1, f"card_row must have ≥1 card, got {len(card_row['cards'])}"
    assert len(card_row["cards"]) <= 5, f"card_row must have ≤5 cards, got {len(card_row['cards'])}"

    # Check chips count
    assert 2 <= len(chips) <= 3, f"Expected 2-3 chips, got {chips}"

    # Check text_delta events were emitted before terminal
    text_events = [e for e in events if e["event"] == "text_delta"]
    assert len(text_events) >= 1, "Expected at least one text_delta event"


# ---------------------------------------------------------------------------
# Test 2: Off-scope message → text only, no card_row, chips present
# ---------------------------------------------------------------------------

def test_off_scope_message_no_card_row():
    """
    'what is the wifi password' must yield a text-only response (no card_row
    component) with redirect chips.
    """
    from backend.app.main import app

    client = TestClient(app)
    resp = client.post("/chat", json={"session_id": "stub-test-2", "message": "what is the wifi password"})
    assert resp.status_code == 200

    events = parse_sse(resp.content)
    last = events[-1]
    assert last["event"] == "components"

    components = last["data"]["components"]
    chips = last["data"]["chips"]

    # No card_row component
    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is None, f"Off-scope response should not contain card_row, got {components}"

    # Chips must be present
    assert len(chips) >= 1, f"Expected redirect chips, got {chips}"

    # Text delta should be a single sentence
    text_events = [e for e in events if e["event"] == "text_delta"]
    assert len(text_events) >= 1, "Expected at least one text_delta"
    full_text = "".join(e["data"]["delta"] for e in text_events)
    assert "support" in full_text.lower() or "cruise" in full_text.lower(), \
        f"Off-scope reply should mention support or redirect to cruises: {full_text!r}"


# ---------------------------------------------------------------------------
# Test 3: Greeting → helpful response + chips
# ---------------------------------------------------------------------------

def test_greeting_returns_helpful_response():
    """
    'hello' must yield a helpful text response and chips (no crash, no empty response).
    """
    from backend.app.main import app

    client = TestClient(app)
    resp = client.post("/chat", json={"session_id": "stub-test-3", "message": "hello"})
    assert resp.status_code == 200

    events = parse_sse(resp.content)
    assert len(events) >= 1, "Expected at least one SSE event"

    last = events[-1]
    assert last["event"] == "components"

    chips = last["data"]["chips"]
    assert len(chips) >= 1, f"Expected chips in greeting response, got {chips}"

    # Response text must be non-empty
    text_events = [e for e in events if e["event"] == "text_delta"]
    assert len(text_events) >= 1, "Expected at least one text_delta event"
    full_text = "".join(e["data"]["delta"] for e in text_events)
    assert len(full_text) > 10, f"Greeting response text too short: {full_text!r}"


# ---------------------------------------------------------------------------
# Test 4 (P8 D1): Scoped itinerary question must route to itinerary Q&A,
# NOT the search branch — even though the cruise name contains 'Cruisetour'.
# ---------------------------------------------------------------------------

def test_scoped_itinerary_question_routes_to_qa_not_search():
    """
    A scoped message like:
      'About the Denali Explorer — Pre-Cruise Cruisetour itinerary
       (denali_explorer): what do we see before Glacier Bay?'
    contains the substring 'cruise', which previously made the search branch
    hijack the turn. It must instead route to the itinerary Q&A path:
      - response text cites 'Day' numbers and earlier ports (Seattle/Juneau/Skagway)
      - NO card_row component is emitted
    """
    from backend.app.main import app

    client = TestClient(app)
    scoped = (
        "About the Denali Explorer — Pre-Cruise Cruisetour itinerary "
        "(denali_explorer): what do we see before Glacier Bay?"
    )
    resp = client.post("/chat", json={"session_id": "stub-test-4", "message": scoped})
    assert resp.status_code == 200

    events = parse_sse(resp.content)
    last = events[-1]
    assert last["event"] == "components"

    components = last["data"]["components"]

    # Must NOT contain a card_row (would mean search hijacked the turn)
    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is None, f"Scoped itinerary question should not yield card_row, got {components}"

    # Should render an itinerary component instead
    itinerary = next((c for c in components if c.get("type") == "itinerary"), None)
    assert itinerary is not None, f"Expected itinerary component, got {components}"

    # Response text must cite Day numbers and earlier ports
    text_events = [e for e in events if e["event"] == "text_delta"]
    assert len(text_events) >= 1, "Expected at least one text_delta event"
    full_text = "".join(e["data"]["delta"] for e in text_events)

    assert "Day" in full_text, f"Response should cite Day numbers: {full_text!r}"
    earlier_ports = ["Seattle", "Juneau", "Skagway"]
    assert all(p in full_text for p in earlier_ports), \
        f"Response should list earlier ports {earlier_ports}: {full_text!r}"
