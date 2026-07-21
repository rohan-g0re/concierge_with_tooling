"""P4 tests — scarcity_for function and template registry audit."""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from app.scarcity import scarcity_for, TEMPLATE_REGISTRY
from app.models import Cruise


# ---------------------------------------------------------------------------
# Test 3: cruise with remaining_at_fare=3 → "3 left at this fare"
# ---------------------------------------------------------------------------

def test_scarcity_remaining_at_fare():
    """cruise with remaining_at_fare=3 → ['3 left at this fare']."""
    cruise = Cruise(
        cruise_id="test-cruise",
        region="alaska",
        name="Test Cruise",
        ship="ms Test",
        embark_port="Seattle",
        nights=7,
        fare_was=2000,
        fare_now=1899,
        popularity_score=0.8,
        photo="test.jpg",
        remaining_at_fare=3,
    )
    signals = scarcity_for(cruise)
    assert "3 left at this fare" in signals, f"Expected '3 left at this fare' in {signals}"


def test_scarcity_historically_sells_out_weeks():
    """cruise with historically_sells_out_weeks=6 → 'tends to sell out ~6 weeks out'."""
    cruise = Cruise(
        cruise_id="test-cruise-2",
        region="alaska",
        name="Test Cruise 2",
        ship="ms Test",
        embark_port="Seattle",
        nights=7,
        fare_was=2000,
        fare_now=1899,
        popularity_score=0.8,
        photo="test.jpg",
        historically_sells_out_weeks=6,
    )
    signals = scarcity_for(cruise)
    assert "tends to sell out ~6 weeks out" in signals, f"Expected sell-out signal in {signals}"


def test_scarcity_holiday_overlap():
    """cruise with holiday_overlap='Memorial Day' → 'overlaps Memorial Day'."""
    cruise = Cruise(
        cruise_id="test-cruise-3",
        region="mexico",
        name="Test Cruise 3",
        ship="ms Test",
        embark_port="Miami",
        nights=5,
        fare_was=1500,
        fare_now=1299,
        popularity_score=0.7,
        photo="test.jpg",
        holiday_overlap="Memorial Day",
    )
    signals = scarcity_for(cruise)
    assert "overlaps Memorial Day" in signals, f"Expected holiday signal in {signals}"


# ---------------------------------------------------------------------------
# Test 4: cruise with no scarcity fields → []
# ---------------------------------------------------------------------------

def test_scarcity_no_fields_returns_empty():
    """cruise with no scarcity fields → []."""
    cruise = Cruise(
        cruise_id="test-cruise-plain",
        region="caribbean",
        name="Plain Cruise",
        ship="ms Plain",
        embark_port="Miami",
        nights=7,
        fare_was=1800,
        fare_now=1599,
        popularity_score=0.6,
        photo="plain.jpg",
        # remaining_at_fare=None (default)
        # historically_sells_out_weeks=None (default)
        # holiday_overlap=None (default)
    )
    signals = scarcity_for(cruise)
    assert signals == [], f"Expected empty list, got {signals}"


def test_scarcity_dict_no_fields_returns_empty():
    """Plain dict with no scarcity fields → []."""
    signals = scarcity_for({"cruise_id": "x", "name": "No fields"})
    assert signals == []


def test_scarcity_dict_with_remaining():
    """Dict with remaining_at_fare → string emitted."""
    signals = scarcity_for({"remaining_at_fare": 5})
    assert "5 left at this fare" in signals


# ---------------------------------------------------------------------------
# Test 5: Audit test — every template's output is derivable from its field value;
# no string emitted when field is absent.
# ---------------------------------------------------------------------------

def test_scarcity_audit_every_template_field_backed():
    """
    Enumerate TEMPLATE_REGISTRY. For each (field_name, fmt_fn):
    1. When field present with test value, string is emitted and contains
       the field value in its output.
    2. When field absent (None), no string is emitted.
    """
    for field_name, fmt_fn in TEMPLATE_REGISTRY:
        # Choose a test value appropriate for the field type
        if "weeks" in field_name:
            test_value = 8
        elif field_name == "remaining_at_fare":
            test_value = 2
        else:
            test_value = "TestHoliday"

        # 1. Field present → string emitted and contains field value
        obj_present = {field_name: test_value}
        signals_present = scarcity_for(obj_present)
        assert len(signals_present) == 1, (
            f"Template '{field_name}': expected exactly 1 signal when field present, got {signals_present}"
        )
        expected_str = fmt_fn(test_value)
        assert signals_present[0] == expected_str, (
            f"Template '{field_name}': expected {expected_str!r}, got {signals_present[0]!r}"
        )
        # The string must incorporate the field value (prove it's data-driven)
        assert str(test_value) in signals_present[0], (
            f"Template '{field_name}': output {signals_present[0]!r} must contain field value {test_value!r}"
        )

        # 2. Field absent → no string emitted
        obj_absent = {}  # empty dict → all fields absent
        signals_absent = scarcity_for(obj_absent)
        # For empty dict, all templates should produce nothing
        # (other templates also absent, so total must be [])

    # Final: empty dict always returns []
    assert scarcity_for({}) == [], "Empty dict must return []"
    # Final: None fields on a model-like object → []
    signals = scarcity_for({"remaining_at_fare": None, "historically_sells_out_weeks": None, "holiday_overlap": None})
    assert signals == [], f"All-None fields must return [], got {signals}"


def test_scarcity_template_registry_has_three_entries():
    """TEMPLATE_REGISTRY has exactly 3 entries covering the 3 documented fields."""
    assert len(TEMPLATE_REGISTRY) == 3
    field_names = [entry[0] for entry in TEMPLATE_REGISTRY]
    assert "remaining_at_fare" in field_names
    assert "historically_sells_out_weeks" in field_names
    assert "holiday_overlap" in field_names


def test_scarcity_multiple_fields_emit_multiple_strings():
    """cruise with both remaining_at_fare and holiday_overlap → 2 strings."""
    cruise = Cruise(
        cruise_id="test-cruise-multi",
        region="alaska",
        name="Multi Scarcity Cruise",
        ship="ms Multi",
        embark_port="Seattle",
        nights=7,
        fare_was=2000,
        fare_now=1899,
        popularity_score=0.9,
        photo="multi.jpg",
        remaining_at_fare=2,
        holiday_overlap="Labor Day",
    )
    signals = scarcity_for(cruise)
    assert len(signals) == 2
    assert "2 left at this fare" in signals
    assert "overlaps Labor Day" in signals
