"""P4 tests — handoff_checkout tool."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.models import Session
from app.catalog.loader import load_catalog
from app.tools.draft import create_draft
from app.tools.handoff import handoff_checkout


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_session(party: int = 2) -> Session:
    return Session(session_id="test-handoff-session", party=party)


# Test 6: handoff_checkout('d1') → {url: '/checkout/d1'}
def test_handoff_checkout_returns_correct_url(catalog):
    """handoff_checkout for a valid draft returns {url: '/checkout/<draft_id>'}."""
    session = make_session()
    r = create_draft(session, {"cruise_id": "denali_explorer"})
    assert "error" not in r, f"create_draft failed: {r}"
    draft_id = r["draft_id"]

    result = handoff_checkout(session, {"draft_id": draft_id})

    assert "error" not in result, f"handoff_checkout failed: {result}"
    assert "url" in result, f"Expected 'url' key in result: {result}"
    assert result["url"] == f"/checkout/{draft_id}", (
        f"Expected '/checkout/{draft_id}', got {result['url']!r}"
    )


def test_handoff_checkout_url_encodes_draft_id():
    """URL encodes the draft_id verbatim in /checkout/<draft_id>."""
    session = make_session()
    # Manually add a draft with a known ID
    from app.models import Draft, DraftStateroom
    draft = Draft(
        draft_id="d1",
        cruise_id="denali_explorer",
        label="Test",
        fare_package="good_to_go",
        stateroom=DraftStateroom(category="Inside"),
        completed_steps=[1],
    )
    session.drafts.append(draft)

    result = handoff_checkout(session, {"draft_id": "d1"})
    assert result == {"url": "/checkout/d1"}, f"Expected {{url: '/checkout/d1'}}, got {result}"


def test_handoff_checkout_unknown_draft_returns_error(catalog):
    """handoff_checkout for unknown draft_id → {error: 'draft_not_found'}."""
    session = make_session()
    result = handoff_checkout(session, {"draft_id": "nonexistent-draft-id"})
    assert result.get("error") == "draft_not_found", f"Expected draft_not_found, got: {result}"
    assert "message" in result


def test_handoff_checkout_missing_draft_id_returns_error():
    """handoff_checkout with no draft_id → {error: 'missing_draft_id'}."""
    session = make_session()
    result = handoff_checkout(session, {})
    assert result.get("error") == "missing_draft_id", f"Expected missing_draft_id, got: {result}"


def test_handoff_checkout_in_tool_registry():
    """compare_drafts and handoff_checkout are registered in TOOL_REGISTRY."""
    from app.tools import TOOL_REGISTRY
    assert "handoff_checkout" in TOOL_REGISTRY, "handoff_checkout must be in TOOL_REGISTRY"
    assert "compare_drafts" in TOOL_REGISTRY, "compare_drafts must be in TOOL_REGISTRY"

    # Verify schemas have required fields
    _, handoff_schema = TOOL_REGISTRY["handoff_checkout"]
    assert handoff_schema["parameters"]["required"] == ["draft_id"]

    _, compare_schema = TOOL_REGISTRY["compare_drafts"]
    assert compare_schema["parameters"]["required"] == ["draft_ids"]
