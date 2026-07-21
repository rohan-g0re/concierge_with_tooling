"""P1 tests — catalog loading and validation."""
from __future__ import annotations

import json
import tempfile
import os
from pathlib import Path

import pytest

# We need the catalog loader and models
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.catalog.loader import load_catalog, CatalogValidationError


@pytest.fixture(scope="module")
def catalog():
    """Load the real catalog once for the module."""
    return load_catalog()


# ---------------------------------------------------------------------------
# Test 1: Catalog counts and regions
# ---------------------------------------------------------------------------

def test_catalog_cruise_count(catalog):
    """Catalog must have at least 24 cruises."""
    assert len(catalog["cruises"]) >= 24, (
        f"Expected >= 24 cruises, got {len(catalog['cruises'])}"
    )


def test_catalog_regions(catalog):
    """All four regions must be present."""
    regions = {c.region for c in catalog["cruises"]}
    assert regions == {"alaska", "mexico", "caribbean", "mediterranean"}, (
        f"Expected 4 regions, got: {regions}"
    )


def test_catalog_alaska_cruisetours(catalog):
    """At least 4 Alaska cruisetours required."""
    alaska_tours = [
        c for c in catalog["cruises"]
        if c.region == "alaska" and c.is_cruisetour
    ]
    assert len(alaska_tours) >= 4, (
        f"Expected >= 4 Alaska cruisetours, got {len(alaska_tours)}"
    )


# ---------------------------------------------------------------------------
# Test 2: Required non-null fields on every cruise
# ---------------------------------------------------------------------------

def test_cruise_required_fields(catalog):
    """Every cruise must have non-null popularity_score, fare_was, fare_now, photo."""
    for cruise in catalog["cruises"]:
        assert cruise.popularity_score is not None, (
            f"cruise {cruise.cruise_id}: popularity_score is None"
        )
        assert cruise.fare_was is not None, (
            f"cruise {cruise.cruise_id}: fare_was is None"
        )
        assert cruise.fare_now is not None, (
            f"cruise {cruise.cruise_id}: fare_now is None"
        )
        assert cruise.photo is not None and cruise.photo != "", (
            f"cruise {cruise.cruise_id}: photo is None or empty"
        )


# ---------------------------------------------------------------------------
# Test 3: Dining venue capacity covers all nights
# ---------------------------------------------------------------------------

def test_dining_capacity_covers_all_nights(catalog):
    """Every dining venue must have capacity_remaining for nights 1..cruise.nights."""
    cruise_nights = {c.cruise_id: c.nights for c in catalog["cruises"]}

    for venue in catalog["dining"]:
        cruise_id = venue.cruise_id
        n_nights = cruise_nights.get(cruise_id)
        if n_nights is None:
            continue  # skip if cruise not found

        covered_nights = {night.night for night in venue.nights}
        expected_nights = set(range(1, n_nights + 1))

        assert covered_nights == expected_nights, (
            f"venue {venue.venue_id} on {cruise_id}: "
            f"expected nights {expected_nights}, got {covered_nights}"
        )


# ---------------------------------------------------------------------------
# Test 6: Malformed catalog raises CatalogValidationError
# ---------------------------------------------------------------------------

def test_malformed_catalog_raises_error():
    """Missing required fields in cruises.json must raise CatalogValidationError."""
    # Create a temp directory with a malformed cruises.json
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Malformed: missing required 'fare_now' field
        bad_cruises = [
            {
                "cruise_id": "bad_cruise",
                "region": "alaska",
                "name": "Bad Cruise",
                "ship": "ms Bad",
                "embark_port": "Seattle, Washington",
                "nights": 7,
                "is_cruisetour": False,
                "fare_was": 1000,
                # fare_now intentionally missing
                "popularity_score": 0.5,
                "photo": "/ports/test.svg",
            }
        ]

        (tmp_path / "cruises.json").write_text(json.dumps(bad_cruises))

        # Write valid stubs for the other 4 files
        (tmp_path / "itineraries.json").write_text("[]")
        (tmp_path / "dining.json").write_text("[]")
        (tmp_path / "land_options.json").write_text("[]")
        (tmp_path / "staterooms.json").write_text("[]")

        with pytest.raises(CatalogValidationError) as exc_info:
            load_catalog(data_dir=tmp_path)

        assert "cruises.json" in str(exc_info.value)
