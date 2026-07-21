"""
P9 tests — GET /session/{session_id} endpoint + set_active_draft tool.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.session_store import get_or_create, update

client = TestClient(app)


def _fresh_session_id() -> str:
    import uuid
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# GET /session/{session_id}
# ---------------------------------------------------------------------------

class TestGetSession:
    def test_returns_empty_session_for_new_id(self):
        sid = _fresh_session_id()
        resp = client.get(f"/session/{sid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid
        assert data["drafts"] == []
        assert data["active_draft_id"] is None
        assert "constraints" in data
        assert "party" in data

    def test_returns_drafts_after_create_draft(self):
        sid = _fresh_session_id()
        # Create a draft via /action
        resp = client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "denali_explorer"}},
        )
        assert resp.status_code == 200
        action_data = resp.json()
        draft_id = action_data["result"]["draft_id"]

        # GET /session should now show the draft
        resp2 = client.get(f"/session/{sid}")
        assert resp2.status_code == 200
        data = resp2.json()
        assert len(data["drafts"]) == 1
        assert data["drafts"][0]["draft_id"] == draft_id
        assert data["drafts"][0]["label"] is not None
        assert data["active_draft_id"] == draft_id

    def test_draft_has_completed_steps(self):
        sid = _fresh_session_id()
        client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "denali_explorer"}},
        )
        data = client.get(f"/session/{sid}").json()
        draft = data["drafts"][0]
        assert isinstance(draft["completed_steps"], list)
        assert 1 in draft["completed_steps"]  # step 1 completed on create

    def test_total_formatted_present(self):
        sid = _fresh_session_id()
        client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "denali_explorer"}},
        )
        data = client.get(f"/session/{sid}").json()
        draft = data["drafts"][0]
        # total_formatted may be None if pricing not computed, but key must exist
        assert "total_formatted" in draft


# ---------------------------------------------------------------------------
# set_active_draft tool
# ---------------------------------------------------------------------------

class TestSetActiveDraft:
    def test_set_active_draft_switches_active(self):
        sid = _fresh_session_id()
        # Create two drafts
        r1 = client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "denali_explorer"}},
        )
        draft_id_1 = r1.json()["result"]["draft_id"]

        r2 = client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "mexico_riviera"}},
        )
        draft_id_2 = r2.json()["result"]["draft_id"]

        # Active should be draft_id_2 (last created)
        data = client.get(f"/session/{sid}").json()
        assert data["active_draft_id"] == draft_id_2

        # Switch back to draft_id_1
        resp = client.post(
            "/action/set_active_draft",
            json={"session_id": sid, "args": {"draft_id": draft_id_1}},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result["active_draft_id"] == draft_id_1

        # Verify session now shows draft_id_1 as active
        data2 = client.get(f"/session/{sid}").json()
        assert data2["active_draft_id"] == draft_id_1

    def test_set_active_draft_unknown_id_returns_error(self):
        sid = _fresh_session_id()
        resp = client.post(
            "/action/set_active_draft",
            json={"session_id": sid, "args": {"draft_id": "nonexistent-id"}},
        )
        assert resp.status_code == 200
        result = resp.json()["result"]
        assert result.get("error") == "draft_not_found"

    def test_set_active_draft_missing_draft_id_returns_error(self):
        sid = _fresh_session_id()
        resp = client.post(
            "/action/set_active_draft",
            json={"session_id": sid, "args": {}},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Missing required arg → top-level validation_error from /action route
        # OR the tool itself returns a missing_draft_id error under "result"
        error = data.get("error") or data.get("result", {}).get("error")
        assert error in ("missing_draft_id", "validation_error")
