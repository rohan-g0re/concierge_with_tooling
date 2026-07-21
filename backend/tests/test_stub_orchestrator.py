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
