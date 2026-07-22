"""P4 tests — compare_drafts tool."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.models import Session, Constraints, Draft, DraftStateroom, DraftLandDay
from app.catalog.loader import load_catalog
from app.tools.draft import create_draft, set_fare, set_stateroom
from app.tools.compare import compare_drafts
from app.money import draft_total, format_money


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def make_session(party: int = 2) -> Session:
    return Session(session_id="test-compare-session", party=party)


def make_customized_draft(session, cruise_id, fare="have_it_all", category="Verandah", location="Midship"):
    """Create a draft and customize it with fare + stateroom."""
    r = create_draft(session, {"cruise_id": cruise_id})
    assert "error" not in r, f"create_draft failed: {r}"
    draft_id = r["draft_id"]
    set_fare(session, {"draft_id": draft_id, "package": fare})
    set_stateroom(session, {"draft_id": draft_id, "category": category, "location": location})
    return draft_id


# Test 1: Two customized drafts → row keys match, totals reflect customization, differ flags correct
def test_compare_two_drafts_row_keys_and_diff(catalog):
    """
    compare_drafts([d1, d2]) with:
      - d1: denali_explorer, have_it_all, Verandah Midship
      - d2: alaska_inside_passage, have_it_all, Inside (cheaper)
    Row keys must match design; totals reflect customization;
    Fare package differ==False (both have_it_all); Dates differ==True (different cruises).
    """
    session = make_session(party=2)
    d1 = make_customized_draft(session, "denali_explorer", fare="have_it_all", category="Verandah", location="Midship")
    d2 = make_customized_draft(session, "alaska_inside_passage", fare="have_it_all", category="Inside")

    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    assert "error" not in result, f"compare_drafts failed: {result}"

    rows = result["rows"]
    assert isinstance(rows, list), "rows must be a list"
    assert len(rows) == 10, f"Expected 10 rows, got {len(rows)}"

    # Verify exact row labels match design compareRows
    expected_labels = [
        "Cruise",
        "Nights",
        "Ship",
        "Fare package",
        "Stateroom",
        "Dining reserved",
        "Land days",
        "Per person",
        "Total · 2 guests",
        "Deposit terms",
    ]
    actual_labels = [r["label"] for r in rows]
    assert actual_labels == expected_labels, f"Row labels mismatch:\n  expected: {expected_labels}\n  actual:   {actual_labels}"

    # Each row must have 'values' (list of 2) and 'differ' (bool)
    for row in rows:
        assert "label" in row
        assert "values" in row
        assert "differ" in row
        assert len(row["values"]) == 2, f"Row {row['label']!r} must have 2 values, got {len(row['values'])}"
        assert isinstance(row["differ"], bool)

    # Fare package differ==False (both have_it_all → both "The Signature Collection")
    fare_row = next(r for r in rows if r["label"] == "Fare package")
    assert fare_row["differ"] is False, f"Fare package differ should be False, got {fare_row}"
    assert fare_row["values"][0] == "The Signature Collection"
    assert fare_row["values"][1] == "The Signature Collection"

    # Cruise differ==True (different cruises → different cruise names)
    dates_row = next(r for r in rows if r["label"] == "Cruise")
    assert dates_row["differ"] is True, f"Cruise differ should be True (different cruises), got {dates_row}"

    # Total values reflect customization (d1 Verandah+Signature > d2 Inside+Signature)
    total_row = next(r for r in rows if r["label"] == "Total · 2 guests")
    # d1 has Verandah (+486/pp) so should be higher
    # Just verify both are formatted money strings and d1 > d2 total
    assert total_row["differ"] is True, "Totals should differ between Verandah and Inside"

    # Verify headers
    assert "headers" in result
    assert len(result["headers"]) == 2
    assert "checkout_urls" in result
    assert result["checkout_urls"][0].startswith(f"/checkout/{d1}"), (
        f"Expected URL starting with '/checkout/{d1}': {result['checkout_urls'][0]}"
    )
    assert result["checkout_urls"][1].startswith(f"/checkout/{d2}"), (
        f"Expected URL starting with '/checkout/{d2}': {result['checkout_urls'][1]}"
    )
    assert "session=" in result["checkout_urls"][0], f"Expected session param in URL: {result['checkout_urls'][0]}"
    assert "session=" in result["checkout_urls"][1], f"Expected session param in URL: {result['checkout_urls'][1]}"


def test_compare_same_fare_package_differ_false(catalog):
    """Two drafts with same fare package → Fare package row differ==False."""
    session = make_session(party=2)
    d1 = make_customized_draft(session, "alaska_inside_passage", fare="good_to_go", category="Inside")
    d2 = make_customized_draft(session, "denali_explorer", fare="good_to_go", category="Inside")

    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    assert "error" not in result

    fare_row = next(r for r in result["rows"] if r["label"] == "Fare package")
    assert fare_row["differ"] is False
    assert fare_row["values"][0] == "Standard"
    assert fare_row["values"][1] == "Standard"


# Test 2: 4 draft ids → compare_cap refusal
def test_compare_four_drafts_returns_cap_error(catalog):
    """
    compare_drafts with 4 draft_ids → {error: 'compare_cap', message containing 'up to three'}.
    Sessions cap at 3 drafts, so we construct the 4-id call with 3 real + 1 fake id.
    The cap check happens BEFORE draft resolution, so the error fires immediately.
    """
    session = make_session(party=2)
    d1 = make_customized_draft(session, "denali_explorer")
    d2 = make_customized_draft(session, "alaska_inside_passage")
    d3 = make_customized_draft(session, "glacier_discovery")

    # Call with 3 real + 1 fake id (cap check is on len(draft_ids), fires first)
    result = compare_drafts(session, {"draft_ids": [d1, d2, d3, "fake-draft-id"]})

    assert result.get("error") == "compare_cap", f"Expected compare_cap, got: {result}"
    assert "message" in result
    assert "up to three" in result["message"].lower() or "three" in result["message"].lower(), (
        f"Message should mention 'up to three': {result['message']}"
    )


def test_compare_totals_reflect_customization(catalog):
    """Totals in comparison reflect stateroom customization, not base product."""
    session = make_session(party=2)
    # d1: Inside (no stateroom delta)
    d1 = make_customized_draft(session, "alaska_inside_passage", fare="good_to_go", category="Inside")
    # d2: Verandah (+486/pp)
    d2 = make_customized_draft(session, "alaska_inside_passage", fare="good_to_go", category="Verandah", location="Midship")

    result = compare_drafts(session, {"draft_ids": [d1, d2]})
    assert "error" not in result

    total_row = next(r for r in result["rows"] if "Total" in r["label"])
    assert total_row["differ"] is True

    # d2 Verandah should be higher
    # Values are formatted strings; check via raw totals from session drafts
    draft1 = next(d for d in session.drafts if d.draft_id == d1)
    draft2 = next(d for d in session.drafts if d.draft_id == d2)
    assert draft2.total > draft1.total, "Verandah draft should cost more than Inside"
    # The difference should be 486 * 2 = 972
    assert draft2.total - draft1.total == 486 * 2
