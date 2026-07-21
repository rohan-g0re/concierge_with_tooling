"""
Unit 5 tests — rich draft identity (R12, R14).

Covers:
  - create_draft without sailing_id → sailing_id/departure_date/return_date all non-null
  - create_draft with explicit sailing_id → stores exactly that sailing
  - create_draft with session.constraints.month=10 → October sailing chosen
  - set_sailing valid → dates updated
  - set_sailing mapper branch doesn't crash
  - set_sailing with invalid sailing → sailing_not_found
  - set_sailing with unknown draft → draft_not_found
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.models import Session, Constraints
from app.catalog.loader import load_catalog
from app.tools.draft import create_draft, set_sailing


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_session(party: int = 2, constraints: Constraints | None = None) -> Session:
    """Create a fresh session with optional constraints."""
    s = Session(session_id="test-unit5", party=party)
    if constraints is not None:
        s.constraints = constraints
    return s


# ---------------------------------------------------------------------------
# create_draft — sailing auto-selection
# ---------------------------------------------------------------------------

class TestCreateDraftSailing:
    def test_no_sailing_arg_assigns_sailing(self, catalog):
        """create_draft without sailing_id → sailing_id, departure_date, return_date all non-null."""
        session = make_session()
        result = create_draft(session, {"cruise_id": "denali_explorer"})
        assert "error" not in result, f"create_draft failed: {result}"
        assert result.get("sailing_id") is not None, "sailing_id must be set"
        assert result.get("departure_date") is not None, "departure_date must be set"
        assert result.get("return_date") is not None, "return_date must be set"

        # Verify stored on draft object too
        draft = session.drafts[0]
        assert draft.sailing_id is not None
        assert draft.departure_date is not None
        assert draft.return_date is not None

    def test_explicit_sailing_id_stores_exactly_that(self, catalog):
        """create_draft with explicit sailing_id → stores exactly that sailing."""
        session = make_session()
        # Use a known sailing from denali_explorer
        target_sailing_id = "denali_explorer-2026-08-05"
        result = create_draft(session, {
            "cruise_id": "denali_explorer",
            "sailing_id": target_sailing_id,
        })
        assert "error" not in result, f"create_draft failed: {result}"
        assert result.get("sailing_id") == target_sailing_id
        assert result.get("departure_date") == "2026-08-05"
        assert result.get("return_date") == "2026-08-17"

        draft = session.drafts[0]
        assert draft.sailing_id == target_sailing_id
        assert draft.departure_date == "2026-08-05"
        assert draft.return_date == "2026-08-17"

    def test_invalid_sailing_id_returns_error(self, catalog):
        """create_draft with invalid sailing_id returns sailing_not_found."""
        session = make_session()
        result = create_draft(session, {
            "cruise_id": "denali_explorer",
            "sailing_id": "totally_bogus_sailing",
        })
        assert result.get("error") == "sailing_not_found", f"Expected sailing_not_found, got: {result}"
        # No draft should have been added
        assert len(session.drafts) == 0

    def test_month_constraint_picks_october_sailing(self, catalog):
        """create_draft with session.constraints.month=10 → picks a sailing in October."""
        constraints = Constraints(month=10)
        session = make_session(constraints=constraints)
        result = create_draft(session, {"cruise_id": "denali_explorer"})
        assert "error" not in result, f"create_draft failed: {result}"
        dep = result.get("departure_date", "")
        # October = month 10
        assert dep.startswith("2026-10-"), (
            f"Expected October departure, got {dep!r}"
        )

    def test_no_constraints_picks_next_upcoming(self, catalog):
        """Without constraints, creates draft with sailing >= ANCHOR_DATE (2026-07-01)."""
        session = make_session()
        result = create_draft(session, {"cruise_id": "denali_explorer"})
        assert "error" not in result
        dep = result.get("departure_date", "")
        assert dep >= "2026-07-01", f"Expected sailing >= anchor date, got {dep!r}"


# ---------------------------------------------------------------------------
# set_sailing
# ---------------------------------------------------------------------------

class TestSetSailing:
    def test_set_sailing_valid_updates_dates(self, catalog):
        """set_sailing with a valid sailing_id → updates departure/return dates on draft."""
        session = make_session()
        r = create_draft(session, {"cruise_id": "denali_explorer"})
        draft_id = r["draft_id"]
        original_sailing = r.get("sailing_id")

        # Pick a different sailing
        new_sailing_id = "denali_explorer-2026-09-02"
        assert new_sailing_id != original_sailing, "Need to pick a different sailing for this test to be meaningful"

        result = set_sailing(session, {"draft_id": draft_id, "sailing_id": new_sailing_id})
        assert "error" not in result, f"set_sailing failed: {result}"
        assert result.get("sailing_id") == new_sailing_id
        assert result.get("departure_date") == "2026-09-02"
        assert result.get("return_date") == "2026-09-14"
        assert result.get("draft_id") == draft_id

        # Verify stored on draft
        draft = session.drafts[0]
        assert draft.sailing_id == new_sailing_id
        assert draft.departure_date == "2026-09-02"
        assert draft.return_date == "2026-09-14"

    def test_set_sailing_invalid_sailing_returns_error(self, catalog):
        """set_sailing with invalid sailing_id → sailing_not_found."""
        session = make_session()
        r = create_draft(session, {"cruise_id": "denali_explorer"})
        draft_id = r["draft_id"]

        result = set_sailing(session, {"draft_id": draft_id, "sailing_id": "bogus_sailing_99"})
        assert result.get("error") == "sailing_not_found", f"Expected sailing_not_found, got: {result}"

    def test_set_sailing_unknown_draft_returns_error(self, catalog):
        """set_sailing with unknown draft_id → draft_not_found."""
        session = make_session()
        result = set_sailing(session, {"draft_id": "nonexistent-draft-id", "sailing_id": "denali_explorer-2026-08-05"})
        assert result.get("error") == "draft_not_found", f"Expected draft_not_found, got: {result}"

    def test_set_sailing_mapper_branch_no_crash(self, catalog):
        """_map_tool_result_to_component('set_sailing', result) returns without crash."""
        from app.llm.gemini_client import _map_tool_result_to_component

        # Valid result — should return None
        result_ok = {
            "draft_id": "d1",
            "sailing_id": "denali_explorer-2026-08-05",
            "departure_date": "2026-08-05",
            "return_date": "2026-08-17",
            "label": "Test Draft",
        }
        component = _map_tool_result_to_component("set_sailing", result_ok)
        assert component is None  # no UI component

        # Error result — should return error component
        result_err = {"error": "sailing_not_found", "message": "Not found"}
        component_err = _map_tool_result_to_component("set_sailing", result_err)
        assert component_err is not None
        assert component_err.get("type") == "error"
