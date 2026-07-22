import json
import pytest
from pathlib import Path

MANIFEST_PATH = Path(__file__).parent / "../../frontend/public/images/manifest.json"

EXPECTED_CRUISES = [
    "denali_explorer", "glacier_discovery", "great_alaskan_explorer", "yukon_denali",
    "alaska_inside_passage", "alaska_glacier_south", "alaska_gold_rush", "alaska_midnight_sun",
    "mexico_riviera", "mexico_pacific", "mexico_yucatan", "mexico_baja",
    "mexico_holiday", "mexico_extended",
    "caribbean_eastern", "caribbean_western", "caribbean_southern", "caribbean_bahamas",
    "caribbean_thanksgiving", "caribbean_grand",
    "med_greek_isles", "med_italy_france", "med_western", "med_adriatic",
    "hawaii_nonstop", "hawaii_neighbor_islands", "hawaii_maui_big_island",
    "bermuda_classic", "bermuda_pink_sand",
    "bahamas_weekend", "bahamas_grand_escape",
]

EXPECTED_STATEROOMS = ["inside", "ocean_view", "verandah", "suite"]

EXPECTED_DINING = ["saffron", "main_dining", "lido"]

EXPECTED_LAND = [
    "coastal_d1", "domed_rail_d2", "motorcoach_d2",
    "denali_lodge_2n", "fairbanks_tour_d4", "skagway_summit_d3",
]


@pytest.fixture(scope="module")
def manifest():
    data = json.loads(MANIFEST_PATH.resolve().read_text(encoding="utf-8"))
    # manifest.json is {"generated": ..., "files": {"path/key.jpg": {"file": ..., "ok": bool}, ...}}
    return data["files"]


def test_manifest_loaded(manifest):
    assert len(manifest) > 0, "manifest.json is empty"


def _check_category(manifest, prefix, expected_ids):
    missing = []
    failed = []
    for id_ in expected_ids:
        key = f"{prefix}/{id_}.jpg"
        if key not in manifest:
            missing.append(key)
        elif not manifest[key].get("ok"):
            failed.append(key)
    if failed:
        print(f"\nFailed (ok=false): {failed}")
    if missing:
        print(f"\nMissing from manifest: {missing}")
    assert len(missing) == 0, f"Missing manifest entries: {missing}"


def test_cruise_images(manifest):
    _check_category(manifest, "cruises", EXPECTED_CRUISES)


def test_stateroom_images(manifest):
    _check_category(manifest, "staterooms", EXPECTED_STATEROOMS)


def test_dining_images(manifest):
    _check_category(manifest, "dining", EXPECTED_DINING)


def test_land_images(manifest):
    _check_category(manifest, "land", EXPECTED_LAND)
