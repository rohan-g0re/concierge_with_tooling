"""
U3 tests — get_step_options returns non-empty components for incomplete steps.

Confirms the machinery reused by the checkout Remaining Steps section works
for steps that have NOT yet been completed by the guest (not just completed ones).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Session, Constraints
from app.session_store import update
from app.tools.draft import create_draft, set_fare

client = TestClient(app)


def make_session(session_id: str | None = None) -> Session:
    return Session(
        session_id=session_id or str(uuid.uuid4()),
        drafts=[],
        active_draft_id=None,
        party=2,
        messages=[],
        constraints=Constraints(),
    )


def _seed_partial_draft(session_id: str, through_step: int, cruise_id: str = "denali_explorer") -> str:
    """Create a draft completed only through `through_step` and persist it."""
    session = make_session(session_id)
    result = create_draft(session, {"cruise_id": cruise_id})
    assert "error" not in result
    did = result["draft_id"]

    if through_step >= 2:
        set_fare(session, {"draft_id": did, "package": "have_it_all"})

    if through_step >= 3:
        from app.tools.draft import set_stateroom
        set_stateroom(session, {"draft_id": did, "category": "Verandah", "location": "Midship"})

    # Steps 4 and 5 intentionally NOT completed — that is the point of this test.
    update(session)
    return did


class TestStepOptionsForIncomplete:
    """
    U3 test set item 1 — backend/tests/test_checkout_steps.py::test_step_options_for_incomplete

    get_step_options (GET /session/{id}/draft/{did}/step/{n}/options) returns
    non-empty `components` for steps 2, 3, 4 of a partial draft (only step 1
    completed), confirming the machinery U3 reuses works for *incomplete* steps.
    """

    def test_step_options_for_incomplete_step2(self):
        """Step 2 options return non-empty components for a draft that has only step 1 done."""
        session_id = str(uuid.uuid4())
        # Only step 1 complete (create_draft adds it automatically).
        session = make_session(session_id)
        result = create_draft(session, {"cruise_id": "denali_explorer"})
        did = result["draft_id"]
        draft = next(d for d in session.drafts if d.draft_id == did)
        # Confirm only step 1 done.
        assert draft.completed_steps == [1]
        update(session)

        resp = client.get(f"/session/{session_id}/draft/{did}/step/2/options")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        comps = body.get("components", [])
        assert len(comps) > 0, f"Step 2 options should be non-empty for incomplete draft; got {comps}"
        types = {c["type"] for c in comps}
        assert "fare_tiles" in types, f"Expected fare_tiles in step 2 components; got {types}"

    def test_step_options_for_incomplete_step3(self):
        """Step 3 options return non-empty components when only steps 1–2 are done."""
        session_id = str(uuid.uuid4())
        did = _seed_partial_draft(session_id, through_step=2)

        resp = client.get(f"/session/{session_id}/draft/{did}/step/3/options")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        comps = body.get("components", [])
        assert len(comps) > 0, f"Step 3 options should be non-empty for incomplete draft; got {comps}"
        types = {c["type"] for c in comps}
        assert "stateroom_picker" in types, f"Expected stateroom_picker in step 3 components; got {types}"

    def test_step_options_for_incomplete_step4(self):
        """Step 4 options return non-empty components when only steps 1–3 are done."""
        session_id = str(uuid.uuid4())
        did = _seed_partial_draft(session_id, through_step=3)

        resp = client.get(f"/session/{session_id}/draft/{did}/step/4/options")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        comps = body.get("components", [])
        assert len(comps) > 0, f"Step 4 options should be non-empty for incomplete draft; got {comps}"
        types = {c["type"] for c in comps}
        assert "dining_tiles" in types, f"Expected dining_tiles in step 4 components; got {types}"

    def test_step_options_for_incomplete_all_three_steps(self):
        """All of steps 2, 3, 4 return components for a draft with only step 1 complete."""
        session_id = str(uuid.uuid4())
        session = make_session(session_id)
        result = create_draft(session, {"cruise_id": "mexico_riviera"})
        did = result["draft_id"]
        update(session)

        for step in (2, 3, 4):
            resp = client.get(f"/session/{session_id}/draft/{did}/step/{step}/options")
            assert resp.status_code == 200, f"Step {step} returned {resp.status_code}: {resp.text}"
            comps = resp.json().get("components", [])
            assert len(comps) > 0, (
                f"Step {step} options must be non-empty for incomplete draft; got {comps}"
            )
