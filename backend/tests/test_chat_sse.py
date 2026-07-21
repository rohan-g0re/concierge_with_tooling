"""
P5 tests — /chat SSE endpoint + Gemini agentic loop.

All tests use a FAKE Gemini client — no real API key or network required.
Tests cover:
  1. SSE framing (text_delta events then terminal components event)
  2. Function call execution for search_cruises → card_row component, 2-3 chips
  3. Observability log captures {tool, latency_ms}
  4. MAX_STEPS guard terminates infinite function_call loops
  5. session.messages persisted after turn
"""
from __future__ import annotations

import json
import types as pytypes
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fake Gemini types — minimal stubs that mimic google.genai.types structures
# ---------------------------------------------------------------------------

class FakePart:
    def __init__(self, *, text=None, function_call=None):
        self.text = text
        self.function_call = function_call


class FakeFunctionCall:
    def __init__(self, name: str, args: dict):
        self.name = name
        self.args = args


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
    """A single streaming chunk with text."""
    def __init__(self, text: str):
        self.candidates = [FakeCandidate([FakePart(text=text)])]


# ---------------------------------------------------------------------------
# Fake genai types module (for FunctionDeclaration, Tool, etc.)
# ---------------------------------------------------------------------------

class FakeTypes:
    """Stub for google.genai.types — only what gemini_client needs."""

    class FunctionDeclaration:
        def __init__(self, name, description="", parameters=None):
            self.name = name
            self.description = description
            self.parameters = parameters

    class Tool:
        def __init__(self, function_declarations=None):
            self.function_declarations = function_declarations or []

    class GenerateContentConfig:
        def __init__(self, tools=None, system_instruction=None):
            self.tools = tools or []
            self.system_instruction = system_instruction

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


# ---------------------------------------------------------------------------
# Fixture: patch google.genai and google.genai.types before importing client
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_genai(monkeypatch):
    """
    Patch google.genai and google.genai.types in sys.modules before any import
    so gemini_client.py never tries to import the real SDK.
    """
    import sys

    fake_genai_module = MagicMock()
    fake_types_module = FakeTypes()

    # Patch sys.modules so `from google import genai` works
    fake_google = MagicMock()
    fake_google.genai = fake_genai_module
    sys.modules.setdefault("google", fake_google)
    sys.modules["google.genai"] = fake_genai_module
    sys.modules["google.genai.types"] = fake_types_module

    yield fake_genai_module


@pytest.fixture()
def reset_client():
    """Reset the lazy _client after each test."""
    import importlib
    # Import and reset
    from backend.app.llm import gemini_client
    old_client = gemini_client._client
    yield gemini_client
    gemini_client._client = old_client


# ---------------------------------------------------------------------------
# Helper: build a fake client that returns a fixed sequence of responses
# ---------------------------------------------------------------------------

def make_fake_client(responses: list, stream_chunks: list[str] | None = None):
    """
    Build a fake genai.Client mock.

    responses: list of FakeResponse objects returned by generate_content (for tool-call steps)
    stream_chunks: list of text strings yielded by generate_content_stream (for final text step)
    """
    client = MagicMock()

    response_iter = iter(responses)

    def fake_generate_content(model, contents, config):
        return next(response_iter)

    def fake_generate_content_stream(model, contents, config):
        chunks = stream_chunks or ["Hello! "]
        return iter([FakeStreamChunk(c) for c in chunks])

    client.models.generate_content.side_effect = fake_generate_content
    client.models.generate_content_stream.side_effect = fake_generate_content_stream
    return client


# ---------------------------------------------------------------------------
# Helper: parse SSE stream bytes into events
# ---------------------------------------------------------------------------

def parse_sse(content: bytes) -> list[dict]:
    """Parse raw SSE bytes into list of {event, data} dicts."""
    events = []
    current = {}
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
# Test 1: SSE framing — text_delta events then terminal components event
# ---------------------------------------------------------------------------

def test_sse_framing():
    """
    A plain text response (no function calls) must yield:
      - one or more text_delta events with {"delta": "..."}
      - exactly one terminal components event with {"components": [...], "chips": [...]}
    The components event must be last.
    """
    from backend.app.llm import gemini_client
    from backend.app.main import app

    # Response with no function calls → triggers streaming
    no_fc_response = FakeResponse([FakeCandidate([FakePart(text=None)])])
    # (no function_call on any part)
    stream_text = ["Hello! ", "I can help you find a cruise.\nCHIPS: [\"Search cruises\", \"View deals\"]"]

    fake_client = make_fake_client([no_fc_response], stream_chunks=stream_text)
    gemini_client.set_client(fake_client)

    client = TestClient(app)
    resp = client.post("/chat", json={"session_id": "test-sse-1", "message": "hi"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    events = parse_sse(resp.content)
    assert len(events) >= 2, f"Expected ≥2 events, got {events}"

    # All but last must be text_delta
    for ev in events[:-1]:
        assert ev["event"] == "text_delta", f"Expected text_delta, got {ev}"
        assert "delta" in ev["data"]

    # Last must be components
    last = events[-1]
    assert last["event"] == "components", f"Last event must be 'components', got {last}"
    assert "components" in last["data"]
    assert "chips" in last["data"]


# ---------------------------------------------------------------------------
# Test 2: Function call → search_cruises → card_row component + chips
# ---------------------------------------------------------------------------

def test_function_call_search_cruises():
    """
    When the model calls search_cruises, the real handler must be executed
    and the result mapped to a card_row component with ≤5 cards.
    Chips must be present (2-3).
    """
    from backend.app.llm import gemini_client
    from backend.app.main import app

    # Step 1: model response with a function_call for search_cruises
    fc = FakeFunctionCall(name="search_cruises", args={"region": "alaska"})
    fc_part = FakePart(function_call=fc)
    fc_response = FakeResponse([FakeCandidate([fc_part])])

    # Step 2: final text response (no function calls)
    text_response = FakeResponse([FakeCandidate([FakePart(text=None)])])

    stream_text = ["Here are some Alaska cruises!\nCHIPS: [\"Show itinerary\", \"Create booking\", \"More options\"]"]

    fake_client = make_fake_client([fc_response, text_response], stream_chunks=stream_text)
    gemini_client.set_client(fake_client)

    client = TestClient(app)
    resp = client.post("/chat", json={"session_id": "test-fc-search", "message": "show me alaska cruises"})
    assert resp.status_code == 200

    events = parse_sse(resp.content)
    last = events[-1]
    assert last["event"] == "components"

    components = last["data"]["components"]
    assert len(components) >= 1, "Expected at least one component from search_cruises"

    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is not None, f"Expected card_row component, got {components}"
    assert len(card_row["cards"]) <= 5, f"card_row must have ≤5 cards, got {len(card_row['cards'])}"

    chips = last["data"]["chips"]
    assert 2 <= len(chips) <= 3, f"Expected 2-3 chips, got {chips}"


# ---------------------------------------------------------------------------
# Test 3: Observability log captures {tool, latency_ms}
# ---------------------------------------------------------------------------

def test_observability_log():
    """
    After a turn that calls search_cruises, the observability log must contain
    an event with event='tool_call', tool='search_cruises', and latency_ms.
    """
    from backend.app.llm import gemini_client
    from backend.app import observability
    from backend.app.main import app

    observability.clear_log()

    fc = FakeFunctionCall(name="search_cruises", args={})
    fc_part = FakePart(function_call=fc)
    fc_response = FakeResponse([FakeCandidate([fc_part])])
    text_response = FakeResponse([FakeCandidate([FakePart(text=None)])])
    stream_text = ["Results ready.\nCHIPS: [\"Next step\", \"Another option\"]"]

    fake_client = make_fake_client([fc_response, text_response], stream_chunks=stream_text)
    gemini_client.set_client(fake_client)

    client = TestClient(app)
    client.post("/chat", json={"session_id": "test-obs", "message": "find cruises"})

    log = observability.get_log()
    tool_events = [e for e in log if e.get("event") == "tool_call"]
    assert len(tool_events) >= 1, f"Expected tool_call events, got {log}"
    evt = tool_events[0]
    assert evt["tool"] == "search_cruises"
    assert "latency_ms" in evt
    assert isinstance(evt["latency_ms"], int)


# ---------------------------------------------------------------------------
# Test 4: MAX_STEPS guard terminates infinite function_call loops
# ---------------------------------------------------------------------------

def test_max_steps_guard():
    """
    If the model returns function_calls indefinitely, the loop must stop after
    MAX_STEPS and return a fallback message without raising an exception.
    """
    from backend.app.llm import gemini_client
    from backend.app.main import app

    MAX_STEPS = gemini_client.MAX_STEPS

    # Always return a function_call — never a final text
    fc = FakeFunctionCall(name="search_cruises", args={})
    fc_part = FakePart(function_call=fc)
    infinite_response = FakeResponse([FakeCandidate([fc_part])])

    call_count = [0]
    original_side_effect = None

    def always_fc(model, contents, config):
        call_count[0] += 1
        return FakeResponse([FakeCandidate([FakePart(function_call=fc)])])

    fake_client = MagicMock()
    fake_client.models.generate_content.side_effect = always_fc
    fake_client.models.generate_content_stream.return_value = iter([])

    gemini_client.set_client(fake_client)

    client = TestClient(app)
    resp = client.post("/chat", json={"session_id": "test-maxsteps", "message": "loop forever"})
    assert resp.status_code == 200

    events = parse_sse(resp.content)
    assert len(events) >= 1

    last = events[-1]
    assert last["event"] == "components"

    # generate_content should have been called at most MAX_STEPS times
    assert call_count[0] <= MAX_STEPS, f"Loop ran {call_count[0]} times, expected ≤{MAX_STEPS}"


# ---------------------------------------------------------------------------
# Test 5: session.messages persisted after turn
# ---------------------------------------------------------------------------

def test_session_messages_persisted():
    """
    After a /chat turn, session.messages must contain the user message
    and the assistant response.
    """
    from backend.app.llm import gemini_client
    from backend.app import session_store
    from backend.app.main import app

    session_id = "test-persist-msgs"
    user_msg = "What cruises do you have?"

    no_fc_response = FakeResponse([FakeCandidate([FakePart(text=None)])])
    stream_text = ["We have many cruises!\nCHIPS: [\"Search Alaska\", \"Search Caribbean\"]"]

    fake_client = make_fake_client([no_fc_response], stream_chunks=stream_text)
    gemini_client.set_client(fake_client)

    client = TestClient(app)
    resp = client.post("/chat", json={"session_id": session_id, "message": user_msg})
    assert resp.status_code == 200

    # Consume the response fully
    _ = resp.content

    session = session_store.get_or_create(session_id)
    assert len(session.messages) >= 2, f"Expected ≥2 messages, got {session.messages}"

    user_msgs = [m for m in session.messages if m.get("role") == "user"]
    model_msgs = [m for m in session.messages if m.get("role") == "model"]

    assert any(m.get("content") == user_msg for m in user_msgs), \
        f"User message not found in {user_msgs}"
    assert len(model_msgs) >= 1, "Expected at least one model message"


# ---------------------------------------------------------------------------
# Test 6: search_cruises card_row uses "results" key (not "cruises")
# Regression for defect: _map_tool_result_to_component was reading result["cruises"]
# but search_cruises returns {"results": [...], "filters": {...}}
# ---------------------------------------------------------------------------

def test_search_cruises_cards_populated():
    """
    When the model calls search_cruises for Alaska, the card_row component
    must contain non-empty cards (catalog has 8 Alaska cruises).
    Previously broken because _map_tool_result_to_component read result.get("cruises")
    instead of result.get("results"), yielding cards=[].
    """
    from backend.app.llm import gemini_client
    from backend.app.main import app

    fc = FakeFunctionCall(name="search_cruises", args={"region": "alaska"})
    fc_part = FakePart(function_call=fc)
    fc_response = FakeResponse([FakeCandidate([fc_part])])
    text_response = FakeResponse([FakeCandidate([FakePart(text=None)])])
    stream_text = ["Here are Alaska cruises!\nCHIPS: [\"View itinerary\", \"Book now\", \"More options\"]"]

    fake_client = make_fake_client([fc_response, text_response], stream_chunks=stream_text)
    gemini_client.set_client(fake_client)

    client = TestClient(app)
    resp = client.post("/chat", json={"session_id": "test-cards-populated", "message": "show me alaska cruises"})
    assert resp.status_code == 200

    events = parse_sse(resp.content)
    last = events[-1]
    assert last["event"] == "components"

    components = last["data"]["components"]
    card_row = next((c for c in components if c.get("type") == "card_row"), None)
    assert card_row is not None, f"Expected card_row, got {components}"
    # Catalog has Alaska cruises — cards must NOT be empty
    assert len(card_row["cards"]) > 0, (
        f"card_row.cards is empty — search_cruises result key mismatch. "
        f"Got card_row={card_row}"
    )
    assert len(card_row["cards"]) <= 5


# ---------------------------------------------------------------------------
# Test 7: CHIPS must never appear in streamed text_delta events
# Regression for defect: raw chunks (including "CHIPS: [...]") were emitted
# before stripping, leaking the marker into the visible stream.
# ---------------------------------------------------------------------------

def test_chips_not_in_streamed_deltas():
    """
    Streamed text_delta events must never contain the literal string "CHIPS:"
    or the JSON chips array.  The CHIPS marker must only influence the terminal
    components event (chips field), never the visible text stream.
    """
    from backend.app.llm import gemini_client
    from backend.app.main import app

    no_fc_response = FakeResponse([FakeCandidate([FakePart(text=None)])])
    # Simulate a realistic stream where CHIPS arrives in a late chunk
    stream_text = [
        "Here are your results. ",
        "Alaska is beautiful in summer.",
        "\nCHIPS: [\"View itinerary\", \"Book now\", \"More options\"]",
    ]

    fake_client = make_fake_client([no_fc_response], stream_chunks=stream_text)
    gemini_client.set_client(fake_client)

    client = TestClient(app)
    resp = client.post("/chat", json={"session_id": "test-chips-hidden", "message": "show alaska"})
    assert resp.status_code == 200

    events = parse_sse(resp.content)

    # Collect all text_delta events
    text_deltas = [ev for ev in events if ev["event"] == "text_delta"]
    assert len(text_deltas) >= 1, "Expected at least one text_delta"

    full_streamed_text = "".join(ev["data"]["delta"] for ev in text_deltas)

    # The CHIPS marker must not appear in the streamed text
    assert "CHIPS:" not in full_streamed_text, (
        f"'CHIPS:' leaked into streamed text_delta. Streamed text was: {full_streamed_text!r}"
    )
    assert "[" not in full_streamed_text or "View itinerary" not in full_streamed_text, (
        f"Chips array content leaked into text_delta. Streamed text was: {full_streamed_text!r}"
    )

    # But the terminal components event must still have chips parsed from it
    last = events[-1]
    assert last["event"] == "components"
    chips = last["data"]["chips"]
    assert len(chips) >= 2, f"Expected chips from CHIPS marker, got {chips}"
