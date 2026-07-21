"""
P13 tests — checkout_entry edge cases, set_active_draft action envelope,
compare_drafts Cruise row label.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.catalog.loader import load_catalog
from app.main import app
from app.models import Session, Constraints, Draft, DraftStateroom
from app.session_store import update
from app.tools.draft import checkout_entry, create_draft, set_fare, set_stateroom
from app.tools.compare import compare_drafts
from app.routes.action import _build_components

client = TestClient(app)


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_session(session_id: str | None = None) -> Session:
    return Session(
        session_id=session_id or str(uuid.uuid4()),
        drafts=[],
        active_draft_id=None,
        party=2,
        messages=[],
        constraints=Constraints(),
    )


def make_draft(session: Session, cruise_id: str = "denali_explorer") -> str:
    result = create_draft(session, {"cruise_id": cruise_id})
    assert "error" not in result
    return result["draft_id"]


# ---------------------------------------------------------------------------
# checkout_entry edge cases
# ---------------------------------------------------------------------------

def test_checkout_entry_empty_steps():
    """No completed steps → entry at step 1."""
    session = make_session()
    did = make_draft(session)
    draft = next(d for d in session.drafts if d.draft_id == did)
    # Remove step 1 that create_draft adds
    draft.completed_steps = []
    assert checkout_entry(draft) == 1


def test_checkout_entry_step1_only():
    """Only step 1 done → entry at step 2."""
    session = make_session()
    did = make_draft(session)
    draft = next(d for d in session.drafts if d.draft_id == did)
    draft.completed_steps = [1]
    assert checkout_entry(draft) == 2


def test_checkout_entry_steps_1_2():
    """Steps 1+2 done → entry at step 3."""
    session = make_session()
    did = make_draft(session)
    draft = next(d for d in session.drafts if d.draft_id == did)
    draft.completed_steps = [1, 2]
    assert checkout_entry(draft) == 3


def test_checkout_entry_steps_1_2_3():
    """Steps 1–3 done → entry at step 4 (classic post-stateroom state)."""
    session = make_session()
    did = make_draft(session)
    draft = next(d for d in session.drafts if d.draft_id == did)
    draft.completed_steps = [1, 2, 3]
    assert checkout_entry(draft) == 4


def test_checkout_entry_steps_1_through_4():
    """Steps 1–4 done → entry at step 5."""
    session = make_session()
    did = make_draft(session)
    draft = next(d for d in session.drafts if d.draft_id == did)
    draft.completed_steps = [1, 2, 3, 4]
    assert checkout_entry(draft) == 5


def test_checkout_entry_all_steps_done():
    """All 5 steps done → returns 6 (sentinel for 'all done')."""
    session = make_session()
    did = make_draft(session)
    draft = next(d for d in session.drafts if d.draft_id == did)
    draft.completed_steps = [1, 2, 3, 4, 5]
    assert checkout_entry(draft) == 6


def test_checkout_entry_out_of_order_steps():
    """Steps in non-sorted order → still returns correct min missing."""
    session = make_session()
    did = make_draft(session)
    draft = next(d for d in session.drafts if d.draft_id == did)
    draft.completed_steps = [3, 1, 2]  # unordered, missing 4 and 5
    assert checkout_entry(draft) == 4


def test_checkout_entry_skipped_step():
    """Steps 1 and 3 done (skipped 2) → entry at 2 (min missing)."""
    session = make_session()
    did = make_draft(session)
    draft = next(d for d in session.drafts if d.draft_id == did)
    draft.completed_steps = [1, 3]
    assert checkout_entry(draft) == 2


# ---------------------------------------------------------------------------
# set_active_draft action envelope via /action route
# ---------------------------------------------------------------------------

def test_set_active_draft_action_returns_envelope():
    """/action/set_active_draft returns {result, components, chips} — not empty body."""
    session_id = str(uuid.uuid4())
    session = make_session(session_id)
    did1 = make_draft(session, "denali_explorer")
    did2 = make_draft(session, "mexico_riviera")
    session.active_draft_id = did1
    update(session)

    resp = client.post(
        "/action/set_active_draft",
        json={"session_id": session_id, "args": {"draft_id": did2}},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Must have the three envelope keys
    assert "result" in body, f"Missing 'result' key: {body}"
    assert "components" in body, f"Missing 'components' key: {body}"
    assert "chips" in body, f"Missing 'chips' key: {body}"


def test_set_active_draft_action_result_has_active_draft_id():
    """/action/set_active_draft result contains active_draft_id."""
    session_id = str(uuid.uuid4())
    session = make_session(session_id)
    did1 = make_draft(session, "denali_explorer")
    did2 = make_draft(session, "mexico_riviera")
    session.active_draft_id = did1
    update(session)

    resp = client.post(
        "/action/set_active_draft",
        json={"session_id": session_id, "args": {"draft_id": did2}},
    )
    body = resp.json()
    assert "error" not in body.get("result", {}), f"Unexpected error: {body}"
    assert body["result"]["active_draft_id"] == did2


def test_set_active_draft_action_chips_not_empty():
    """/action/set_active_draft chips list is non-empty."""
    session_id = str(uuid.uuid4())
    session = make_session(session_id)
    did1 = make_draft(session, "denali_explorer")
    did2 = make_draft(session, "mexico_riviera")
    update(session)

    resp = client.post(
        "/action/set_active_draft",
        json={"session_id": session_id, "args": {"draft_id": did2}},
    )
    body = resp.json()
    assert isinstance(body.get("chips"), list)
    assert len(body["chips"]) > 0, "chips should not be empty"


def test_set_active_draft_action_not_found_returns_error_result():
    """/action/set_active_draft with unknown draft_id returns error in result."""
    session_id = str(uuid.uuid4())
    session = make_session(session_id)
    update(session)

    resp = client.post(
        "/action/set_active_draft",
        json={"session_id": session_id, "args": {"draft_id": "nonexistent"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Tool-level errors come back wrapped in the envelope with result.error
    assert "result" in body
    assert body["result"].get("error") == "draft_not_found"


# ---------------------------------------------------------------------------
# compare_drafts Cruise row label (was "Dates")
# ---------------------------------------------------------------------------

def test_compare_cruise_row_label_not_dates(catalog):
    """compare_drafts rows must use 'Cruise' label, not 'Dates'."""
    session = make_session()
    did1 = make_draft(session, "denali_explorer")
    set_fare(session, {"draft_id": did1, "package": "have_it_all"})
    did2 = make_draft(session, "mexico_riviera")
    set_fare(session, {"draft_id": did2, "package": "good_to_go"})

    result = compare_drafts(session, {"draft_ids": [did1, did2]})
    assert "error" not in result
    labels = [r["label"] for r in result["rows"]]
    assert "Dates" not in labels, f"'Dates' label must not appear; got: {labels}"
    assert "Cruise" in labels, f"'Cruise' label must appear; got: {labels}"


def test_compare_cruise_row_values_are_cruise_names(catalog):
    """Cruise row values are cruise names (meaningful, not blank)."""
    session = make_session()
    did1 = make_draft(session, "denali_explorer")
    set_fare(session, {"draft_id": did1, "package": "good_to_go"})
    did2 = make_draft(session, "mexico_riviera")
    set_fare(session, {"draft_id": did2, "package": "good_to_go"})

    result = compare_drafts(session, {"draft_ids": [did1, did2]})
    cruise_row = next(r for r in result["rows"] if r["label"] == "Cruise")
    for val in cruise_row["values"]:
        assert val, f"Cruise row value should be non-empty, got: {val!r}"


# ---------------------------------------------------------------------------
# GET /session/{id}/draft/{draft_id}/step/{n}/options — inline-edit descriptors
#
# These back the checkout resume page's real inline editing (P13 test 4). The
# endpoint reuses the SAME descriptor builders as /action (R21 parity), so
# checkout renders identical, wired components via the componentRegistry.
# ---------------------------------------------------------------------------

def _seed_full_draft(session_id: str, cruise_id: str = "denali_explorer") -> str:
    """Create a draft with steps 1–3 complete and persist it to the store."""
    session = make_session(session_id)
    did = make_draft(session, cruise_id)
    set_fare(session, {"draft_id": did, "package": "have_it_all"})
    set_stateroom(session, {"draft_id": did, "category": "Verandah", "location": "Midship"})
    update(session)
    return did


def test_step_options_step2_returns_fare_tiles_with_current_package():
    """Step 2 → fare_tiles descriptor pre-selecting the draft's saved package."""
    session_id = str(uuid.uuid4())
    did = _seed_full_draft(session_id)

    resp = client.get(f"/session/{session_id}/draft/{did}/step/2/options")
    assert resp.status_code == 200
    body = resp.json()
    assert body["step"] == 2
    assert body["draft_id"] == did
    comps = body["components"]
    fare = next(c for c in comps if c["type"] == "fare_tiles")
    assert fare["draft_id"] == did
    # Pre-selected to the saved package so the component initializes correctly.
    assert fare["current_package"] == "have_it_all"
    # Two standard fare options, identical to the /action chain.
    ids = {o["id"] for o in fare["options"]}
    assert ids == {"good_to_go", "have_it_all"}


def test_step_options_step3_returns_stateroom_picker():
    """Step 3 → stateroom_picker descriptor with catalog categories + locations."""
    session_id = str(uuid.uuid4())
    did = _seed_full_draft(session_id)

    resp = client.get(f"/session/{session_id}/draft/{did}/step/3/options")
    assert resp.status_code == 200
    body = resp.json()
    picker = next(c for c in body["components"] if c["type"] == "stateroom_picker")
    assert picker["draft_id"] == did
    assert len(picker["categories"]) > 0
    assert picker["locations"] == ["Forward", "Midship", "Aft"]


def test_step_options_step4_returns_dining_and_land_for_cruisetour():
    """Step 4 → dining_tiles (always) + land_builder (cruisetour only)."""
    session_id = str(uuid.uuid4())
    did = _seed_full_draft(session_id, "denali_explorer")

    resp = client.get(f"/session/{session_id}/draft/{did}/step/4/options")
    assert resp.status_code == 200
    types = {c["type"] for c in resp.json()["components"]}
    assert "dining_tiles" in types
    # denali_explorer is a cruisetour → land_builder present.
    assert "land_builder" in types


def test_step_options_step4_no_land_for_non_cruisetour():
    """Non-cruisetour draft at step 4 → dining_tiles but no land_builder."""
    session_id = str(uuid.uuid4())
    did = _seed_full_draft(session_id, "mexico_riviera")

    resp = client.get(f"/session/{session_id}/draft/{did}/step/4/options")
    assert resp.status_code == 200
    types = {c["type"] for c in resp.json()["components"]}
    assert "dining_tiles" in types
    assert "land_builder" not in types


def test_step_options_unsupported_step_400():
    """Steps outside {2,3,4} (e.g. 1, 5) return 400 unsupported_step."""
    session_id = str(uuid.uuid4())
    did = _seed_full_draft(session_id)

    resp = client.get(f"/session/{session_id}/draft/{did}/step/1/options")
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "unsupported_step"


def test_step_options_unknown_draft_404():
    """Unknown draft_id → 404 draft_not_found."""
    session_id = str(uuid.uuid4())
    make_session(session_id)
    update(Session(session_id=session_id))

    resp = client.get(f"/session/{session_id}/draft/nonexistent/step/2/options")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "draft_not_found"


def test_step_options_parity_with_action_fare_options():
    """Descriptors come from the SAME builders /action uses (R21 single source)."""
    from app.routes.action import _fare_tiles_options

    session_id = str(uuid.uuid4())
    did = _seed_full_draft(session_id)

    resp = client.get(f"/session/{session_id}/draft/{did}/step/2/options")
    fare = next(c for c in resp.json()["components"] if c["type"] == "fare_tiles")
    # Options are byte-for-byte the action route's _fare_tiles_options().
    assert fare["options"] == _fare_tiles_options()
