"""
P15 tests — /feedback and /debug routes.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.observability import clear_log, get_log

client = TestClient(app)


def setup_function():
    clear_log()


def test_feedback_thumbs_down():
    resp = client.post("/feedback", json={
        "message_id": "msg-001",
        "vote": "down",
        "state_snapshot": {"constraints": {"region": "caribbean"}},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["vote"] == "down"
    assert data["message_id"] == "msg-001"


def test_feedback_thumbs_up():
    resp = client.post("/feedback", json={
        "message_id": "msg-002",
        "vote": "up",
        "state_snapshot": {},
    })
    assert resp.status_code == 200
    assert resp.json()["vote"] == "up"


def test_feedback_logged_in_observability():
    clear_log()
    client.post("/feedback", json={
        "message_id": "msg-log",
        "vote": "down",
        "state_snapshot": {"test": True},
    })
    log = get_log()
    feedback_events = [e for e in log if e.get("event") == "feedback"]
    assert len(feedback_events) == 1
    assert feedback_events[0]["vote"] == "down"
    assert feedback_events[0]["message_id"] == "msg-log"
    assert feedback_events[0]["state_snapshot"] == {"test": True}


def test_debug_returns_session_fields():
    resp = client.get("/debug?session_id=debug-test-session")
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert "constraints" in data
    assert "party" in data
    assert "active_draft_id" in data
    assert "drafts" in data
    assert "tool_log" in data
    assert "messages_count" in data


def test_debug_default_session():
    resp = client.get("/debug")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == "demo"


def test_debug_tool_log_after_feedback():
    clear_log()
    client.post("/feedback", json={
        "message_id": "msg-debug",
        "vote": "up",
        "state_snapshot": {},
    })
    resp = client.get("/debug?session_id=demo")
    data = resp.json()
    # tool_log should contain the feedback event
    feedback_in_log = [e for e in data["tool_log"] if e.get("event") == "feedback"]
    assert len(feedback_in_log) >= 1
