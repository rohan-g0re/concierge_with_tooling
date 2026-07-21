"""
Unit 5 tests — rich session snapshot (R13) + GET /session rich fields (R14).

Covers:
  - _build_session_snapshot with a draft → blob contains region, dep/ret dates, nights, total
  - GET /session via TestClient: bare draft → new fields present, addons_note absent
  - GET /session: draft with add-ons (fare pkg + stateroom upgrade + dining) → addons_note reflects delta
  - GET /session: total_formatted = draft-held total (not catalog base fare)
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.session_store import get_or_create, update
from app.models import Session, Constraints
from app.catalog.loader import load_catalog
from app.tools.draft import create_draft, set_fare, set_stateroom
from app.tools.dining import reserve_dining
from app.money import format_money

client = TestClient(app)


def _sid() -> str:
    return str(uuid.uuid4())


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


# ---------------------------------------------------------------------------
# Snapshot tests
# ---------------------------------------------------------------------------

class TestSessionSnapshot:
    def test_snapshot_with_draft_contains_region_and_dates(self, catalog):
        """_build_session_snapshot with a draft → contains region, dep, ret, nights, total."""
        from app.llm.gemini_client import _build_session_snapshot

        session = Session(session_id="snap-test-1", party=2)
        result = create_draft(session, {"cruise_id": "denali_explorer"})
        assert "error" not in result

        snapshot = _build_session_snapshot(session)

        # Must contain region
        assert "region=alaska" in snapshot, f"region not in snapshot:\n{snapshot}"
        # Must contain port info
        assert "Seattle" in snapshot, f"embark_port not in snapshot:\n{snapshot}"
        # Must contain departure date
        assert "dep=2026-" in snapshot, f"dep not in snapshot:\n{snapshot}"
        # Must contain return date
        assert "ret=2026-" in snapshot, f"ret not in snapshot:\n{snapshot}"
        # Must contain nights
        assert "nights=12" in snapshot, f"nights not in snapshot:\n{snapshot}"
        # Must contain total (formatted)
        assert "US$" in snapshot or "total=" in snapshot, f"total not in snapshot:\n{snapshot}"

    def test_snapshot_total_matches_draft_total(self, catalog):
        """Snapshot total string matches format_money(draft.total)."""
        from app.llm.gemini_client import _build_session_snapshot

        session = Session(session_id="snap-test-2", party=2)
        result = create_draft(session, {"cruise_id": "denali_explorer"})
        assert "error" not in result

        draft = session.drafts[0]
        expected_total = format_money(draft.total)
        snapshot = _build_session_snapshot(session)

        assert expected_total in snapshot, (
            f"Expected total {expected_total!r} in snapshot:\n{snapshot}"
        )

    def test_snapshot_legacy_draft_no_dates_graceful(self, catalog):
        """Snapshot handles draft with departure_date=None gracefully (legacy drafts)."""
        from app.llm.gemini_client import _build_session_snapshot
        from app.models import Draft, DraftStateroom

        session = Session(session_id="snap-test-3", party=2)
        # Manually create a draft without sailing dates (simulating legacy)
        draft = Draft(
            draft_id="legacy-draft-id",
            cruise_id="denali_explorer",
            label="Legacy Draft",
            fare_package="good_to_go",
            stateroom=DraftStateroom(category="Inside"),
            completed_steps=[1],
            sailing_id=None,
            departure_date=None,
            return_date=None,
            total=5364,
        )
        session.drafts.append(draft)
        session.active_draft_id = draft.draft_id

        # Should not raise
        snapshot = _build_session_snapshot(session)
        assert "dep=?" in snapshot, f"Expected dep=? for legacy draft:\n{snapshot}"
        assert "ret=?" in snapshot, f"Expected ret=? for legacy draft:\n{snapshot}"


# ---------------------------------------------------------------------------
# GET /session rich fields
# ---------------------------------------------------------------------------

class TestGetSessionRichFields:
    def test_bare_draft_has_new_fields(self):
        """GET /session: bare draft (just created) has region, embark_port, departure_date, return_date, nights."""
        sid = _sid()
        resp = client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "denali_explorer"}},
        )
        assert resp.status_code == 200

        data = client.get(f"/session/{sid}").json()
        assert len(data["drafts"]) == 1
        draft = data["drafts"][0]

        assert draft.get("region") == "alaska", f"region wrong: {draft.get('region')}"
        assert "Seattle" in (draft.get("embark_port") or ""), f"embark_port wrong: {draft.get('embark_port')}"
        assert draft.get("departure_date") is not None, "departure_date must not be null"
        assert draft.get("return_date") is not None, "return_date must not be null"
        assert draft.get("nights") == 12, f"nights wrong: {draft.get('nights')}"

    def test_bare_draft_addons_note_absent(self):
        """GET /session: bare draft (Inside, good_to_go, no add-ons) → addons_note null/absent."""
        sid = _sid()
        client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "denali_explorer"}},
        )
        data = client.get(f"/session/{sid}").json()
        draft = data["drafts"][0]
        # For a bare draft: total = cruise.fare_now * party (no add-ons)
        # addons_note should be null/None
        assert draft.get("addons_note") is None, (
            f"addons_note should be None for bare draft, got: {draft.get('addons_note')}"
        )

    def test_total_formatted_is_draft_held_total(self):
        """GET /session: total_formatted reflects draft-held total (includes all add-ons)."""
        sid = _sid()
        # Create draft
        r1 = client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "denali_explorer"}},
        )
        draft_id = r1.json()["result"]["draft_id"]

        # Upgrade to have_it_all
        client.post(
            "/action/set_fare",
            json={"session_id": sid, "args": {"draft_id": draft_id, "package": "have_it_all"}},
        )

        # Get session
        data = client.get(f"/session/{sid}").json()
        draft = data["drafts"][0]

        # total_formatted should reflect have_it_all pricing (> base fare * party)
        # denali_explorer: fare_now=2682, nights=12, party=2
        # have_it_all adds 55*12*2=1320 → total should be (2682+660)*2 = 6684
        base_total = 2682 * 2  # 5364
        assert draft.get("total_formatted") is not None
        # The total must be greater than base (because have_it_all was selected)
        # Format: "US$ X,XXX" — parse out number
        tf = draft["total_formatted"].replace("US$ ", "").replace(",", "")
        assert int(tf) > base_total, (
            f"total_formatted {draft['total_formatted']} should exceed base {base_total}"
        )

    def test_addons_note_present_with_stateroom_upgrade(self):
        """GET /session: draft with Verandah upgrade → addons_note present and reflects delta."""
        sid = _sid()
        # Create draft for alaska_inside_passage (7 nights, fare_now=1198 for simple math)
        r1 = client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "alaska_inside_passage"}},
        )
        draft_id = r1.json()["result"]["draft_id"]

        # Set Verandah stateroom (delta=+486/pp)
        client.post(
            "/action/set_stateroom",
            json={"session_id": sid, "args": {"draft_id": draft_id, "category": "Verandah"}},
        )

        data = client.get(f"/session/{sid}").json()
        draft = data["drafts"][0]

        addons_note = draft.get("addons_note")
        assert addons_note is not None, (
            "addons_note should be present for draft with stateroom upgrade"
        )
        assert "add-ons" in addons_note, f"addons_note format wrong: {addons_note!r}"
        assert "US$" in addons_note, f"addons_note should include formatted amount: {addons_note!r}"

    def test_addons_note_with_dining(self):
        """GET /session: draft with dining reservation → addons_note reflects dining cost."""
        sid = _sid()
        # Create draft
        r1 = client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "denali_explorer"}},
        )
        draft_id = r1.json()["result"]["draft_id"]

        # Reserve dining
        client.post(
            "/action/reserve_dining",
            json={"session_id": sid, "args": {"draft_id": draft_id, "venue_id": "saffron", "night": 9}},
        )

        data = client.get(f"/session/{sid}").json()
        draft = data["drafts"][0]

        addons_note = draft.get("addons_note")
        assert addons_note is not None, (
            "addons_note should be present when dining is reserved"
        )
        assert "US$" in addons_note, f"addons_note should include formatted amount: {addons_note!r}"

    def test_session_response_has_all_new_fields(self):
        """GET /session: response includes all new Unit 5 fields at the draft level."""
        sid = _sid()
        client.post(
            "/action/create_draft",
            json={"session_id": sid, "args": {"cruise_id": "denali_explorer"}},
        )
        data = client.get(f"/session/{sid}").json()
        draft = data["drafts"][0]

        for field in ("region", "embark_port", "departure_date", "return_date", "nights", "addons_note"):
            assert field in draft, f"Field {field!r} missing from GET /session draft"
