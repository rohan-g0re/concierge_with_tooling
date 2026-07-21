"""
P14 tests — Voice parity (OpenAI GPT Realtime).

Tests:
  1. POST /voice/token with unset/placeholder key → unavailable state (no crash).
  2. POST /voice/token with fake key (monkeypatched) → correct response shape
     (available, client_secret, model, voice, tools).
  3. tools list from token endpoint contains all 12 TOOL_REGISTRY entries in
     OpenAI Realtime format (type=function, name, description, parameters).
  4. _key_is_set() helper: empty → False, placeholder → False, real → True.
  5. Voice-originated tool call relayed through POST /action/{tool} produces
     same envelope + system_event as tap-path (R21 relay parity).
  6. _build_realtime_tools() keys match TOOL_REGISTRY keys exactly.

No live OpenAI or Gemini calls — all network mocked via monkeypatch / respx or
httpx.MockTransport.
"""
from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Patch google.genai so the app imports without a real key (same pattern as
# test_action_parity.py)
# ---------------------------------------------------------------------------

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
    from app.main import app
    return TestClient(app)


def first_cruise_id():
    from app.catalog.loader import load_catalog
    catalog = load_catalog()
    return catalog["cruises"][0].cruise_id


# ---------------------------------------------------------------------------
# Test 1: Unset / placeholder key → voice_unavailable state
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key_value", ["", "your_openai_key_here", "your_key"])
def test_voice_token_unavailable_when_key_missing(key_value, monkeypatch):
    """POST /voice/token with missing or placeholder key returns unavailable state."""
    from app import config as config_module

    # Force settings to return a placeholder/empty key
    from app.config import Settings
    fake_settings = Settings(openai_api_key=key_value, gemini_api_key="fake")
    monkeypatch.setattr(config_module, "get_settings", lambda: fake_settings)

    # Also patch routes/voice.py's get_settings
    import app.routes.voice as voice_module
    monkeypatch.setattr(voice_module, "get_settings", lambda: fake_settings)

    client = make_client()
    resp = client.post("/voice/token")
    assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["available"] is False
    assert data["reason"] == "voice_unavailable"
    assert "message" in data
    # Must not leak the key
    assert key_value not in json.dumps(data) or key_value == ""


# ---------------------------------------------------------------------------
# Test 2: Fake key via monkeypatch → correct response shape
# ---------------------------------------------------------------------------

def test_voice_token_shape_with_fake_key(monkeypatch):
    """
    With a real-looking (non-placeholder) key and a mocked httpx call,
    /voice/token returns {available, client_secret, model, voice, tools}.
    """
    import httpx
    from app.config import Settings
    import app.routes.voice as voice_module
    import app.config as config_module

    fake_settings = Settings(openai_api_key="sk-fake-key-for-testing", gemini_api_key="fake")
    monkeypatch.setattr(voice_module, "get_settings", lambda: fake_settings)
    monkeypatch.setattr(config_module, "get_settings", lambda: fake_settings)

    # Mock the OpenAI Realtime sessions API response
    fake_openai_response = {
        "id": "sess_test123",
        "client_secret": {
            "value": "ek_test_ephemeral_token_abc123",
            "expires_at": 1700000000,
        },
        "model": "gpt-4o-realtime-preview-2024-12-17",
        "voice": "alloy",
    }

    # Create a simple mock response that won't fail on raise_for_status
    class MockResponse:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return fake_openai_response

    class MockAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            return MockResponse()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    client = make_client()
    resp = client.post("/voice/token")
    assert resp.status_code == 200, f"Expected 200 got {resp.status_code}: {resp.text}"
    data = resp.json()

    # Shape assertions
    assert data["available"] is True
    assert "client_secret" in data
    assert "value" in data["client_secret"]
    assert "expires_at" in data["client_secret"]
    assert data["model"] == "gpt-4o-realtime-preview-2024-12-17"
    assert data["voice"] == "alloy"
    assert "tools" in data
    assert isinstance(data["tools"], list)
    assert len(data["tools"]) > 0

    # Ensure the raw standing key is NOT in the response
    assert "sk-fake-key-for-testing" not in json.dumps(data)


# ---------------------------------------------------------------------------
# Test 3: Tools list contains all TOOL_REGISTRY entries in OpenAI format
# ---------------------------------------------------------------------------

def test_voice_token_tools_match_registry(monkeypatch):
    """
    The tools array in the token response must contain one entry per
    TOOL_REGISTRY key, in OpenAI Realtime format: {type, name, description, parameters}.
    """
    import httpx
    from app.config import Settings
    import app.routes.voice as voice_module

    fake_settings = Settings(openai_api_key="sk-fake-key-for-testing", gemini_api_key="fake")
    monkeypatch.setattr(voice_module, "get_settings", lambda: fake_settings)

    fake_openai_response = {
        "client_secret": {"value": "ek_test", "expires_at": 9999999999},
    }

    class MockResponse3:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return fake_openai_response

    class MockAsyncClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, **kwargs):
            return MockResponse3()

    monkeypatch.setattr(httpx, "AsyncClient", MockAsyncClient)

    from app.tools import TOOL_REGISTRY

    client = make_client()
    resp = client.post("/voice/token")
    assert resp.status_code == 200
    data = resp.json()

    tools = data["tools"]
    tool_names = {t["name"] for t in tools}
    registry_names = set(TOOL_REGISTRY.keys())

    assert tool_names == registry_names, (
        f"Tool name mismatch.\n  In token: {sorted(tool_names)}\n  In registry: {sorted(registry_names)}"
    )

    for tool in tools:
        assert tool["type"] == "function", f"Tool {tool['name']} must have type='function'"
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool


# ---------------------------------------------------------------------------
# Test 4: _key_is_set() helper
# ---------------------------------------------------------------------------

def test_key_is_set_helper():
    """_key_is_set returns False for empty or placeholder keys, True for real-looking keys."""
    from app.routes.voice import _key_is_set

    assert _key_is_set("") is False
    assert _key_is_set("your_openai_key_here") is False
    assert _key_is_set("your_key") is False
    assert _key_is_set("your_") is False
    assert _key_is_set("sk-realkey123") is True
    assert _key_is_set("sk-proj-abc") is True


# ---------------------------------------------------------------------------
# Test 5: Voice-originated relay parity (R21)
#   A voice-originated tool call relayed through POST /action/{tool} produces
#   the same envelope + system_event as a tap-path call.
# ---------------------------------------------------------------------------

def test_voice_relay_parity_via_action_bridge():
    """
    R21: voice tool calls relay through POST /action/{tool} (same handlers).
    This test simulates the frontend voiceClient relaying a voice-originated
    tool call through the action bridge and asserts:
    1. Response envelope shape matches: {result, components, chips}
    2. system_event is appended to session.messages
    3. Draft state == tap-path state (deep-equal parity)
    """
    from app import session_store
    from app.models import Session
    from app.tools.draft import create_draft, set_fare

    client = make_client()

    # --- Simulate voice path (relay through /action) ---
    voice_session_id = "test-p14-voice-relay"
    cruise_id = first_cruise_id()

    # Voice: create draft (step 1) via action bridge
    resp1 = client.post(
        "/action/create_draft",
        json={"session_id": voice_session_id, "args": {"cruise_id": cruise_id}},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert "result" in data1 and "components" in data1 and "chips" in data1
    assert "error" not in data1["result"]
    voice_draft_id = data1["result"]["draft_id"]

    # Voice: set_fare (step 2) via action bridge
    resp2 = client.post(
        "/action/set_fare",
        json={"session_id": voice_session_id, "args": {"draft_id": voice_draft_id, "package": "have_it_all"}},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert "result" in data2 and "components" in data2 and "chips" in data2
    assert "error" not in data2["result"]

    # Retrieve voice session state
    voice_session = session_store.get_or_create(voice_session_id)
    voice_draft = next(d for d in voice_session.drafts if d.draft_id == voice_draft_id)

    # Check system_events were appended
    system_events = [m for m in voice_session.messages if m.get("role") == "system_event"]
    assert len(system_events) >= 2, f"Expected ≥2 system_events, got: {system_events}"

    # --- Simulate tap path (direct handler, same as P6 parity test) ---
    tap_session = Session(session_id="test-p14-tap-path")
    create_result = create_draft(tap_session, {"cruise_id": cruise_id})
    assert "error" not in create_result
    tap_draft_id = create_result["draft_id"]
    fare_result = set_fare(tap_session, {"draft_id": tap_draft_id, "package": "have_it_all"})
    assert "error" not in fare_result
    tap_draft = next(d for d in tap_session.drafts if d.draft_id == tap_draft_id)

    # --- Deep-equal parity (voice relay == tap path) ---
    voice_dict = voice_draft.model_dump()
    tap_dict = tap_draft.model_dump()
    voice_dict.pop("draft_id")
    tap_dict.pop("draft_id")

    for key in ["fare_package", "stateroom", "dining", "land_days", "completed_steps", "total"]:
        assert voice_dict.get(key) == tap_dict.get(key), (
            f"R21 parity failure on '{key}': voice={voice_dict.get(key)!r} vs tap={tap_dict.get(key)!r}"
        )


# ---------------------------------------------------------------------------
# Test 6: _build_realtime_tools keys match TOOL_REGISTRY
# ---------------------------------------------------------------------------

def test_build_realtime_tools_matches_registry():
    """_build_realtime_tools() returns one entry per TOOL_REGISTRY key."""
    from app.routes.voice import _build_realtime_tools
    from app.tools import TOOL_REGISTRY

    tools = _build_realtime_tools()
    names = {t["name"] for t in tools}
    assert names == set(TOOL_REGISTRY.keys())

    for tool in tools:
        assert tool["type"] == "function"
        assert isinstance(tool["description"], str)
        assert isinstance(tool["parameters"], dict)
