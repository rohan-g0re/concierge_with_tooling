"""P1 tests — money formatting and draft total calculation."""
from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.money import format_money, draft_total
from app.catalog.loader import load_catalog
from app.models import (
    Draft,
    DraftStateroom,
    DraftLandDay,
    FARE_PACKAGE_PER_PERSON_PER_NIGHT,
)


# ---------------------------------------------------------------------------
# Test 4: format_money
# ---------------------------------------------------------------------------

def test_format_money_1899():
    assert format_money(1899) == "US$ 1,899"


def test_format_money_8092():
    assert format_money(8092) == "US$ 8,092"


def test_format_money_3828():
    assert format_money(3828) == "US$ 3,828"


def test_format_money_zero():
    assert format_money(0) == "US$ 0"


# ---------------------------------------------------------------------------
# Test 5: Denali reference draft total == 8092
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


@pytest.fixture
def denali_reference_draft():
    """
    Reference draft per design:
      cruise: denali_explorer (fare_now=2682 base "from", 12 nights)
      fare_package: have_it_all (Signature Collection, +55/pp/night)
      stateroom: Verandah (+486)
      dining: Saffron night 9 (price_per_guest=38)
      land_days: 4 days × $45/guest = $180/guest
      party: 2 guests

    Math:
      2682 + (55 × 12) + 486 = 2682 + 660 + 486 = 3828/person
      3828 × 2 = 7656
      38 × 2 = 76 (Saffron)
      4 × 45 × 2 = 360 (land)
      total = 7656 + 76 + 360 = 8092
    """
    draft = Draft(
        draft_id="test_denali_ref",
        cruise_id="denali_explorer",
        label="Denali Explorer Reference",
        fare_package="have_it_all",
        stateroom=DraftStateroom(category="Verandah", location="Midship"),
        dining=["saffron:night_9"],
        land_days=[
            DraftLandDay(day=1, option_id="coastal_d1"),
            DraftLandDay(day=2, option_id="domed_rail_d2"),
            DraftLandDay(day=3, option_id="denali_lodge_2n"),
            DraftLandDay(day=4, option_id="fairbanks_tour_d4"),
        ],
        completed_steps=[],
    )
    return draft


def test_denali_reference_total(catalog, denali_reference_draft):
    """Denali reference draft must total exactly US$ 8,092."""
    total = draft_total(denali_reference_draft, catalog, party=2)
    assert total == 8092, (
        f"Expected Denali reference total 8092, got {total}. "
        f"Check: fare_now=2682, package=55*12=660, verandah_delta=486, "
        f"saffron=38/guest, 4_land_days=45/guest/day, party=2"
    )


# ---------------------------------------------------------------------------
# Regression: Signature Collection package contributes 55 * nights * party
# ---------------------------------------------------------------------------

def _draft(fare_package: str) -> Draft:
    d = Draft(
        draft_id=f"test_{fare_package}",
        cruise_id="denali_explorer",
        label="pkg-delta",
        fare_package=fare_package,
        stateroom=DraftStateroom(category="Verandah", location="Midship"),
        dining=["saffron:night_9"],
        land_days=[
            DraftLandDay(day=1, option_id="coastal_d1"),
            DraftLandDay(day=2, option_id="domed_rail_d2"),
            DraftLandDay(day=3, option_id="denali_lodge_2n"),
            DraftLandDay(day=4, option_id="fairbanks_tour_d4"),
        ],
        completed_steps=[],
    )
    return d


def test_package_delta_equals_55_times_nights_times_party(catalog):
    """have_it_all minus good_to_go == 55 * nights * party (the package delta)."""
    have = draft_total(_draft("have_it_all"), catalog, party=2)
    good = draft_total(_draft("good_to_go"), catalog, party=2)

    cruise = next(c for c in catalog["cruises"] if c.cruise_id == "denali_explorer")
    party = 2
    expected_delta = FARE_PACKAGE_PER_PERSON_PER_NIGHT * cruise.nights * party

    assert have - good == expected_delta, (
        f"Package delta {have - good} != {expected_delta} "
        f"(55 * {cruise.nights} nights * {party} party)"
    )
    # good_to_go must add zero package cost
    assert good == 8092 - expected_delta


def test_invalid_fare_package_rejected():
    """A fare_package outside the Literal set must raise a validation error."""
    with pytest.raises(Exception):
        Draft(
            draft_id="bad",
            cruise_id="denali_explorer",
            label="bad",
            fare_package="premium_plus",  # not a valid FarePackage
            stateroom=DraftStateroom(category="Inside"),
        )
