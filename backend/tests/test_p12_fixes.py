"""
P12 fix-pass tests — Opus fix for failed live-Gemini verification.

Covers:
  A. Session snapshot injected into Gemini `contents` (draft ids/labels/state)
     so the live model references real state instead of hallucinating ids.
  B. compare_drafts defense-in-depth default resolution:
     - missing draft_ids → all session drafts
     - empty draft_ids → all session drafts
     - unknown/hallucinated ids → filtered; fall back to all session drafts
     - <2 valid drafts after fallback → polite no_drafts error
  C. (error copy mapping is verified in the frontend via tsc + component;
     the polite no_drafts message is asserted here as the backend contract.)
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.catalog.loader import load_catalog
from app.models import Session, Constraints
from app.tools.compare import compare_drafts
from app.tools.draft import create_draft, set_fare, set_stateroom


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_session():
    return Session(
        session_id=str(uuid.uuid4()),
        drafts=[],
        active_draft_id=None,
        party=2,
        messages=[],
        constraints=Constraints(),
    )


def make_alaska(session):
    did = create_draft(session, {"cruise_id": "denali_explorer"})["draft_id"]
    set_fare(session, {"draft_id": did, "package": "have_it_all"})
    set_stateroom(session, {"draft_id": did, "category": "Verandah", "location": "Midship"})
    return did


def make_mexico(session):
    did = create_draft(session, {"cruise_id": "mexico_riviera"})["draft_id"]
    set_fare(session, {"draft_id": did, "package": "good_to_go"})
    return did


# ---------------------------------------------------------------------------
# B. compare_drafts default resolution (defense in depth)
# ---------------------------------------------------------------------------

def test_compare_missing_draft_ids_uses_all_session_drafts(catalog):
    """No draft_ids arg → compare all session drafts."""
    session = make_session()
    d1 = make_alaska(session)
    d2 = make_mexico(session)
    result = compare_drafts(session, {})
    assert "error" not in result, f"unexpected error: {result}"
    header_ids = {h["draft_id"] for h in result["headers"]}
    assert header_ids == {d1, d2}


def test_compare_empty_draft_ids_uses_all_session_drafts(catalog):
    """Empty draft_ids list → compare all session drafts."""
    session = make_session()
    d1 = make_alaska(session)
    d2 = make_mexico(session)
    result = compare_drafts(session, {"draft_ids": []})
    assert "error" not in result, f"unexpected error: {result}"
    assert len(result["headers"]) == 2


def test_compare_hallucinated_ids_fall_back_to_all(catalog):
    """All-unknown ids (model hallucination) → fall back to session drafts."""
    session = make_session()
    d1 = make_alaska(session)
    d2 = make_mexico(session)
    result = compare_drafts(session, {"draft_ids": ["ghost-1", "ghost-2"]})
    assert "error" not in result, f"unexpected error: {result}"
    header_ids = {h["draft_id"] for h in result["headers"]}
    assert header_ids == {d1, d2}


def test_compare_partial_unknown_ids_filtered_then_fallback(catalog):
    """1 valid + 1 unknown id → <2 valid → fall back to all session drafts."""
    session = make_session()
    d1 = make_alaska(session)
    d2 = make_mexico(session)
    result = compare_drafts(session, {"draft_ids": [d1, "ghost"]})
    assert "error" not in result, f"unexpected error: {result}"
    # After filter only d1 valid (<2) → fallback to all → both drafts
    assert len(result["headers"]) == 2


def test_compare_two_valid_ids_respected(catalog):
    """Two valid ids explicitly passed → those exact drafts compared."""
    session = make_session()
    d1 = make_alaska(session)
    d2 = make_mexico(session)
    _d3 = create_draft(session, {"cruise_id": "glacier_discovery"})["draft_id"]
    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    assert "error" not in result
    header_ids = {h["draft_id"] for h in result["headers"]}
    assert header_ids == {d1, d2}


def test_compare_fewer_than_two_drafts_polite_error(catalog):
    """Only one draft in session → polite no_drafts error (not raw)."""
    session = make_session()
    make_alaska(session)
    result = compare_drafts(session, {})
    assert result.get("error") == "no_drafts"
    # Polite, sentence-like copy (contains a space, not a bare code)
    assert " " in result.get("message", "")
    assert "two drafts" in result["message"].lower()


def test_compare_no_drafts_at_all_polite_error(catalog):
    """Empty session → polite no_drafts error."""
    session = make_session()
    result = compare_drafts(session, {"draft_ids": ["ghost"]})
    assert result.get("error") == "no_drafts"


def test_compare_cap_still_enforced_on_raw_request(catalog):
    """4 requested ids → compare_cap fires before default resolution."""
    session = make_session()
    d1 = create_draft(session, {"cruise_id": "denali_explorer"})["draft_id"]
    d2 = create_draft(session, {"cruise_id": "mexico_riviera"})["draft_id"]
    d3 = create_draft(session, {"cruise_id": "glacier_discovery"})["draft_id"]
    result = compare_drafts(session, {"draft_ids": [d1, d2, d3, "fake"]})
    assert result.get("error") == "compare_cap"


def test_compare_more_than_three_session_drafts_capped_on_fallback(catalog):
    """If model omits ids but session has >3 drafts, fallback caps at 3."""
    session = make_session()
    create_draft(session, {"cruise_id": "denali_explorer"})
    create_draft(session, {"cruise_id": "mexico_riviera"})
    create_draft(session, {"cruise_id": "glacier_discovery"})
    # Only 3 drafts allowed by create_draft cap, but verify fallback respects 3.
    result = compare_drafts(session, {})
    assert "error" not in result
    assert len(result["headers"]) <= 3


# ---------------------------------------------------------------------------
# A. Session snapshot injected into Gemini contents
# ---------------------------------------------------------------------------

def _fake_types_module():
    """Minimal google.genai.types stub capturing Content/Part text."""
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
            self.description = description
            self.parameters = parameters

    class Tool:
        def __init__(self, function_declarations=None):
            self.function_declarations = function_declarations or []

    class GenerateContentConfig:
        def __init__(self, tools=None, system_instruction=None):
            self.tools = tools or []
            self.system_instruction = system_instruction

    mod = MagicMock()
    mod.Part = Part
    mod.Content = Content
    mod.FunctionDeclaration = FunctionDeclaration
    mod.Tool = Tool
    mod.GenerateContentConfig = GenerateContentConfig
    return mod


@pytest.fixture()
def patch_genai_types(monkeypatch):
    import sys
    fake_types = _fake_types_module()
    fake_genai = MagicMock()
    # `from google.genai import types` resolves `types` as an ATTRIBUTE of the
    # google.genai module object — so it must point at our fake types module,
    # not an auto-generated child mock.
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


def _make_capturing_client():
    """
    Fake client that captures the `contents` passed to generate_content, then
    returns a plain text (no function call) response so the loop terminates.
    """
    captured = {}

    def gen(model, contents, config):
        captured["contents"] = contents
        # No function call → final text turn
        part = MagicMock()
        part.text = None
        part.function_call = None
        cand = MagicMock()
        cand.content.parts = [part]
        resp = MagicMock()
        resp.candidates = [cand]
        return resp

    def gen_stream(model, contents, config):
        return iter([_CapturingChunk("Done.\nCHIPS: [\"a\", \"b\"]")])

    client = MagicMock()
    client.models.generate_content.side_effect = gen
    client.models.generate_content_stream.side_effect = gen_stream
    return client, captured


def test_snapshot_injected_into_contents(patch_genai_types, catalog):
    """
    The session snapshot (draft ids, labels, cruise names, party) must be
    injected into the `contents` sent to the live model.
    """
    from app.llm import gemini_client

    old = gemini_client._client
    try:
        session = make_session()
        d1 = make_alaska(session)
        d2 = make_mexico(session)

        client, captured = _make_capturing_client()
        gemini_client.set_client(client)

        gemini_client.run_turn(session, "Compare my drafts")

        # Flatten all text parts sent to the model
        texts = []
        for content in captured["contents"]:
            for part in content.parts:
                if getattr(part, "text", None):
                    texts.append(part.text)
        blob = "\n".join(texts)

        assert "session state" in blob, f"snapshot header missing: {blob!r}"
        # Real draft ids must be present so the model can reference them
        assert d1 in blob, "alaska draft id not in snapshot"
        assert d2 in blob, "mexico draft id not in snapshot"
        # Party and completed steps context
        assert "party=2" in blob
    finally:
        gemini_client.set_client(old)


def test_snapshot_present_with_no_drafts(patch_genai_types, catalog):
    """Snapshot is injected even with no drafts (states '(none yet)')."""
    from app.llm import gemini_client

    old = gemini_client._client
    try:
        session = make_session()
        client, captured = _make_capturing_client()
        gemini_client.set_client(client)

        gemini_client.run_turn(session, "Hi")

        texts = [
            part.text
            for content in captured["contents"]
            for part in content.parts
            if getattr(part, "text", None)
        ]
        blob = "\n".join(texts)
        assert "session state" in blob
        assert "none yet" in blob
    finally:
        gemini_client.set_client(old)


# ---------------------------------------------------------------------------
# C. compare_drafts tool result → comparison component (gemini path)
# ---------------------------------------------------------------------------

def _make_compare_calling_client(fake_types, draft_ids: list):
    """
    Fake client that simulates Gemini calling compare_drafts in one step,
    then returning a text response on the next.
    """
    call_count = [0]

    class FakeFC:
        name = "compare_drafts"
        args = {"draft_ids": draft_ids}

    def gen(model, contents, config):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: return a function call for compare_drafts
            part = fake_types.Part()
            part.function_call = FakeFC()
            part.text = None
            cand = MagicMock()
            cand.content = fake_types.Content(role="model", parts=[part])
            resp = MagicMock()
            resp.candidates = [cand]
            return resp
        else:
            # Second call: no function call → trigger streaming text
            part = fake_types.Part(text=None)
            part.function_call = None
            cand = MagicMock()
            cand.content.parts = [part]
            resp = MagicMock()
            resp.candidates = [cand]
            return resp

    def gen_stream(model, contents, config):
        return iter([_CapturingChunk("Here is your comparison!\nCHIPS: [\"Book Alaska\", \"Book Mexico\"]")])

    client = MagicMock()
    client.models.generate_content.side_effect = gen
    client.models.generate_content_stream.side_effect = gen_stream
    return client


def test_compare_drafts_tool_result_maps_to_comparison_component(patch_genai_types, catalog):
    """
    When Gemini calls compare_drafts, the tool result must be mapped to a
    component descriptor of type 'comparison' (not omitted). This verifies
    _map_tool_result_to_component handles compare_drafts.
    """
    from app.llm import gemini_client

    old = gemini_client._client
    try:
        session = make_session()
        d1 = make_alaska(session)
        d2 = make_mexico(session)

        client = _make_compare_calling_client(patch_genai_types, [d1, d2])
        gemini_client.set_client(client)

        result = gemini_client.run_turn(session, "Compare my drafts")

        components = result["components"]
        assert len(components) >= 1, "expected at least one component from compare_drafts call"
        comp = next((c for c in components if c.get("type") == "comparison"), None)
        assert comp is not None, (
            f"No 'comparison' component found; got: {components}"
        )
        assert "rows" in comp, "comparison component missing 'rows'"
        assert "headers" in comp, "comparison component missing 'headers'"
        assert len(comp["headers"]) == 2, (
            f"expected 2 headers, got {len(comp['headers'])}"
        )
        # Verify tool_calls tracking
        assert "compare_drafts" in result["tool_calls"]
    finally:
        gemini_client.set_client(old)
