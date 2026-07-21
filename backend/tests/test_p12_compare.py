"""
P12 tests — compare_drafts + set_active_draft + compare descriptor via action.
"""
import uuid
import pytest

from app.catalog.loader import load_catalog
from app.models import Session, Constraints
from app.tools.compare import compare_drafts
from app.tools.set_active_draft import set_active_draft
from app.tools.draft import create_draft, set_fare, set_stateroom
from app.routes.action import _build_components


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


def make_draft(session, cruise_id):
    """Create a draft via create_draft tool and return draft_id."""
    result = create_draft(session, {"cruise_id": cruise_id})
    assert "error" not in result, f"create_draft failed: {result}"
    return result["draft_id"]


def make_alaska_draft(session, catalog):
    """Create a fully customized Alaska (denali_explorer) draft."""
    did = make_draft(session, "denali_explorer")
    set_fare(session, {"draft_id": did, "package": "have_it_all"})
    set_stateroom(session, {"draft_id": did, "category": "Verandah", "location": "Midship"})
    return did


def make_mexico_draft(session, catalog):
    """Create a partially customized Mexico (mexico_riviera) draft — fare only."""
    did = make_draft(session, "mexico_riviera")
    set_fare(session, {"draft_id": did, "package": "good_to_go"})
    return did


# ---------------------------------------------------------------------------
# compare_drafts — basic structure
# ---------------------------------------------------------------------------

def test_compare_drafts_returns_10_rows(catalog):
    session = make_session()
    d1 = make_alaska_draft(session, catalog)
    d2 = make_mexico_draft(session, catalog)
    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    assert "error" not in result, f"compare_drafts error: {result}"
    rows = result["rows"]
    assert len(rows) == 10, f"Expected 10 rows, got {len(rows)}: {[r['label'] for r in rows]}"


def test_compare_drafts_row_labels(catalog):
    session = make_session()
    d1 = make_alaska_draft(session, catalog)
    d2 = make_mexico_draft(session, catalog)
    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    labels = [r["label"] for r in result["rows"]]
    expected = ["Dates", "Nights", "Ship", "Fare package", "Stateroom", "Dining reserved", "Land days", "Per person"]
    for lbl in expected:
        assert lbl in labels, f"Missing row label: {lbl}"


def test_compare_drafts_differ_flag_fare_package(catalog):
    """Alaska uses have_it_all, Mexico uses good_to_go — fare package row must differ."""
    session = make_session()
    d1 = make_alaska_draft(session, catalog)
    d2 = make_mexico_draft(session, catalog)
    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    fare_row = next((r for r in result["rows"] if r["label"] == "Fare package"), None)
    assert fare_row is not None
    assert fare_row["differ"] is True, "Fare packages differ — differ flag should be True"


def test_compare_drafts_same_fare_no_differ(catalog):
    """Two drafts with same fare package — fare row differ must be False."""
    session = make_session()
    d1 = make_draft(session, "denali_explorer")
    set_fare(session, {"draft_id": d1, "package": "have_it_all"})
    d2 = make_draft(session, "mexico_riviera")
    set_fare(session, {"draft_id": d2, "package": "have_it_all"})
    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    fare_row = next((r for r in result["rows"] if r["label"] == "Fare package"), None)
    assert fare_row is not None
    assert fare_row["differ"] is False, "Same fare packages — differ flag should be False"


def test_compare_drafts_cap_4_returns_error(catalog):
    """Attempting to compare 4 drafts returns compare_cap error."""
    # Need 4 sessions with 4 draft IDs — we fake draft IDs since cap is checked on len
    # But compare_drafts also resolves drafts from session, so we need real ones.
    # Create 3 drafts (max allowed) then try with 4 fake IDs
    session = make_session()
    d1 = make_draft(session, "denali_explorer")
    d2 = make_draft(session, "mexico_riviera")
    d3 = make_draft(session, "glacier_discovery")
    # 4th draft doesn't exist — but cap check happens first
    result = compare_drafts(session, {"draft_ids": [d1, d2, d3, "fake_id"]})
    assert result.get("error") == "compare_cap", f"Expected compare_cap, got: {result}"
    assert "three" in result.get("message", "").lower(), f"Message should mention 'three': {result}"


def test_compare_drafts_total_reflects_customization(catalog):
    """Total row values must reflect customized totals, not base fares."""
    session = make_session()
    d1 = make_alaska_draft(session, catalog)  # have_it_all + Verandah
    d2 = make_mexico_draft(session, catalog)  # good_to_go only

    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    # Get the total row (label contains "Total")
    total_row = next((r for r in result["rows"] if "Total" in r["label"]), None)
    assert total_row is not None
    vals = total_row["values"]
    assert len(vals) == 2
    # Alaska (have_it_all + Verandah, 12 nights, 2 pax) should be more than Mexico (good_to_go only)
    # Just verify they're not equal (they're different cruises with different configs)
    assert vals[0] != vals[1], f"Totals should differ for differently configured drafts: {vals}"


def test_compare_drafts_headers(catalog):
    """Headers contain draft_id, label, ship for each draft."""
    session = make_session()
    d1 = make_alaska_draft(session, catalog)
    d2 = make_mexico_draft(session, catalog)
    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    headers = result["headers"]
    assert len(headers) == 2
    for h in headers:
        assert "draft_id" in h
        assert "label" in h
        assert "ship" in h


def test_compare_drafts_checkout_urls(catalog):
    """checkout_urls has one URL per draft, each containing the draft_id."""
    session = make_session()
    d1 = make_alaska_draft(session, catalog)
    d2 = make_mexico_draft(session, catalog)
    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    urls = result["checkout_urls"]
    assert len(urls) == 2
    assert d1 in urls[0], f"First URL should contain {d1}: {urls[0]}"
    assert d2 in urls[1], f"Second URL should contain {d2}: {urls[1]}"


# ---------------------------------------------------------------------------
# set_active_draft
# ---------------------------------------------------------------------------

def test_set_active_draft_switches_active(catalog):
    session = make_session()
    d1 = make_draft(session, "denali_explorer")
    d2 = make_draft(session, "mexico_riviera")
    session.active_draft_id = d1

    result = set_active_draft(session, {"draft_id": d2})
    assert "error" not in result
    assert session.active_draft_id == d2
    assert result["active_draft_id"] == d2


def test_set_active_draft_not_found(catalog):
    session = make_session()
    result = set_active_draft(session, {"draft_id": "nonexistent"})
    assert result.get("error") == "draft_not_found"


def test_set_active_draft_missing_arg(catalog):
    session = make_session()
    result = set_active_draft(session, {})
    assert result.get("error") == "missing_draft_id"


# ---------------------------------------------------------------------------
# Draft independence — customizing one draft doesn't touch the other
# ---------------------------------------------------------------------------

def test_draft_independence(catalog):
    """Customizing Alaska draft does not change Mexico draft."""
    session = make_session()
    d_alaska = make_draft(session, "denali_explorer")
    d_mexico = make_draft(session, "mexico_riviera")

    # Customize Alaska
    set_fare(session, {"draft_id": d_alaska, "package": "have_it_all"})
    set_stateroom(session, {"draft_id": d_alaska, "category": "Suite", "location": "Aft"})

    # Mexico draft should still be at defaults
    mexico = next(d for d in session.drafts if d.draft_id == d_mexico)
    assert mexico.fare_package in ("good_to_go", "standard", None, ""), \
        f"Mexico fare should be default, got: {mexico.fare_package}"
    # Mexico stateroom should not be Suite
    assert mexico.stateroom.category != "Suite", \
        f"Mexico stateroom should not be Suite, got: {mexico.stateroom.category}"


# ---------------------------------------------------------------------------
# compare_drafts via _build_components (action route integration)
# ---------------------------------------------------------------------------

def test_compare_drafts_component_descriptor(catalog):
    """_build_components('compare_drafts', result, session) → comparison descriptor."""
    session = make_session()
    d1 = make_alaska_draft(session, catalog)
    d2 = make_mexico_draft(session, catalog)
    result = compare_drafts(session, {"draft_ids": [d1, d2]})

    components = _build_components("compare_drafts", result, session)
    assert len(components) == 1
    comp = components[0]
    assert comp["type"] == "comparison"
    assert "rows" in comp
    assert "headers" in comp
    assert "checkout_urls" in comp


def test_compare_drafts_error_component(catalog):
    """compare_drafts error → error component from _build_components."""
    session = make_session()
    result = {"error": "compare_cap", "message": "up to three"}
    components = _build_components("compare_drafts", result, session)
    assert len(components) == 1
    assert components[0]["type"] == "error"
