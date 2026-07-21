"""Unit 2 tests — sailing schema, 6-region catalog, seed determinism."""
from __future__ import annotations

import sys
from datetime import timedelta, date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.catalog.loader import load_catalog
from app.catalog.seed_sailings import _generate_sailings, DEMO_ANCHOR
from app.models import Session, Constraints
from app.tools.draft import create_draft


@pytest.fixture(scope="module")
def catalog():
    """Load the real catalog once for the module."""
    return load_catalog()


# ---------------------------------------------------------------------------
# 1. load_catalog() succeeds; every cruise has >= 8 sailings
# ---------------------------------------------------------------------------

def test_catalog_loads(catalog):
    """load_catalog() must succeed and return a dict with cruises key."""
    assert "cruises" in catalog
    assert len(catalog["cruises"]) > 0


def test_every_cruise_has_min_sailings(catalog):
    """Every cruise must have at least 8 sailings."""
    for cruise in catalog["cruises"]:
        assert len(cruise.sailings) >= 8, (
            f"Cruise {cruise.cruise_id} has only {len(cruise.sailings)} sailings"
        )


# ---------------------------------------------------------------------------
# 2. Every sailing: return_date - departure_date == cruise.nights
# ---------------------------------------------------------------------------

def test_sailing_date_spans(catalog):
    """return_date - departure_date must equal cruise.nights for every sailing."""
    for cruise in catalog["cruises"]:
        expected_delta = timedelta(days=cruise.nights)
        for sailing in cruise.sailings:
            dep = date.fromisoformat(sailing.departure_date)
            ret = date.fromisoformat(sailing.return_date)
            actual_delta = ret - dep
            assert actual_delta == expected_delta, (
                f"Cruise {cruise.cruise_id}, sailing {sailing.sailing_id}: "
                f"expected {expected_delta}, got {actual_delta}"
            )


# ---------------------------------------------------------------------------
# 3. Regions set == 6 regions; 30 <= len(cruises) <= 40
# ---------------------------------------------------------------------------

def test_catalog_has_six_regions(catalog):
    """Catalog must have exactly the 6 expected regions."""
    regions = {c.region for c in catalog["cruises"]}
    expected = {"alaska", "mexico", "caribbean", "mediterranean", "hawaii", "bermuda_bahamas"}
    assert regions == expected, f"Expected exactly {expected}, got: {regions}"


def test_catalog_cruise_count_range(catalog):
    """Total cruise count must be between 30 and 40."""
    count = len(catalog["cruises"])
    assert 30 <= count <= 40, f"Expected 30–40 cruises, got {count}"


# ---------------------------------------------------------------------------
# 4. Hawaii nights 10–15; bermuda_bahamas nights 5–7
# ---------------------------------------------------------------------------

def test_hawaii_nights_range(catalog):
    """All Hawaii cruises must have nights in range [10, 15]."""
    hawaii = [c for c in catalog["cruises"] if c.region == "hawaii"]
    assert len(hawaii) >= 1, "No hawaii cruises found"
    for cruise in hawaii:
        assert 10 <= cruise.nights <= 15, (
            f"Hawaii cruise {cruise.cruise_id} has nights={cruise.nights}, expected 10–15"
        )


def test_bermuda_bahamas_nights_range(catalog):
    """All bermuda_bahamas cruises must have nights in range [5, 7]."""
    bb = [c for c in catalog["cruises"] if c.region == "bermuda_bahamas"]
    assert len(bb) >= 1, "No bermuda_bahamas cruises found"
    for cruise in bb:
        assert 5 <= cruise.nights <= 7, (
            f"Bermuda/Bahamas cruise {cruise.cruise_id} has nights={cruise.nights}, expected 5–7"
        )


# ---------------------------------------------------------------------------
# 5. All sailing_ids unique across catalog
# ---------------------------------------------------------------------------

def test_sailing_ids_unique(catalog):
    """sailing_id must be globally unique across all cruises."""
    all_ids: list[str] = []
    for cruise in catalog["cruises"]:
        for sailing in cruise.sailings:
            all_ids.append(sailing.sailing_id)
    assert len(all_ids) == len(set(all_ids)), (
        f"Duplicate sailing_ids found: {len(all_ids) - len(set(all_ids))} duplicates"
    )


# ---------------------------------------------------------------------------
# 6. Determinism: call generator twice → equal sailing lists
# ---------------------------------------------------------------------------

def test_sailing_generation_is_deterministic():
    """Calling _generate_sailings twice must produce identical results."""
    cruise_id = "hawaii_nonstop"
    region = "hawaii"
    nights = 15

    first = _generate_sailings(cruise_id, region, nights)
    second = _generate_sailings(cruise_id, region, nights)

    assert first == second, "Sailing generation is not deterministic"


def test_sailing_generation_deterministic_all_regions():
    """Determinism check across multiple regions."""
    test_cases = [
        ("alaska_test", "alaska", 7),
        ("mexico_test", "mexico", 7),
        ("caribbean_test", "caribbean", 7),
        ("med_test", "mediterranean", 10),
        ("hawaii_test", "hawaii", 12),
        ("bb_test", "bermuda_bahamas", 6),
    ]
    for cruise_id, region, nights in test_cases:
        first = _generate_sailings(cruise_id, region, nights)
        second = _generate_sailings(cruise_id, region, nights)
        assert first == second, f"Non-deterministic for region={region}"


# ---------------------------------------------------------------------------
# 7. create_draft for a new-region cruise returns no error and numeric total
# ---------------------------------------------------------------------------

def test_create_draft_for_new_hawaii_cruise(catalog):
    """create_draft for a hawaii cruise must succeed with a numeric total."""
    hawaii = [c for c in catalog["cruises"] if c.region == "hawaii"]
    assert len(hawaii) >= 1, "No hawaii cruises in catalog"

    cruise = hawaii[0]
    session = Session(
        session_id="test-session-hawaii",
        constraints=Constraints(party=2),
        party=2,
    )
    result = create_draft(session, {"cruise_id": cruise.cruise_id})

    assert "error" not in result, f"create_draft returned error: {result}"
    assert isinstance(result.get("total"), int), (
        f"Expected numeric total, got: {result.get('total')}"
    )
    assert result["total"] > 0, "Total must be positive"


def test_create_draft_for_new_bermuda_bahamas_cruise(catalog):
    """create_draft for a bermuda_bahamas cruise must succeed with a numeric total."""
    bb = [c for c in catalog["cruises"] if c.region == "bermuda_bahamas"]
    assert len(bb) >= 1, "No bermuda_bahamas cruises in catalog"

    cruise = bb[0]
    session = Session(
        session_id="test-session-bb",
        constraints=Constraints(party=2),
        party=2,
    )
    result = create_draft(session, {"cruise_id": cruise.cruise_id})

    assert "error" not in result, f"create_draft returned error: {result}"
    assert isinstance(result.get("total"), int), (
        f"Expected numeric total, got: {result.get('total')}"
    )
    assert result["total"] > 0, "Total must be positive"
