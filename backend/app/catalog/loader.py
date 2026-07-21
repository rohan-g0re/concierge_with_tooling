"""
Compass — Catalog loader.

Loads and validates all 5 JSON catalog files at application boot.
Raises CatalogValidationError with a descriptive message on malformed data.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..models import (
    Cruise,
    ItineraryDay,
    DiningVenue,
    LandOption,
    StateroomCategory,
)

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------

class CatalogValidationError(Exception):
    """Raised when any catalog JSON file fails Pydantic validation."""


# ---------------------------------------------------------------------------
# Module-level catalog cache (populated at import / boot)
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent / "data"

_catalog: dict[str, list[Any]] | None = None


def _load_json(filename: str) -> list[dict]:
    """Read and parse a JSON file from the data directory."""
    path = _DATA_DIR / filename
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise CatalogValidationError(f"Catalog file not found: {path}")
    except json.JSONDecodeError as exc:
        raise CatalogValidationError(f"Invalid JSON in {filename}: {exc}")
    if not isinstance(data, list):
        raise CatalogValidationError(
            f"{filename} must contain a JSON array, got {type(data).__name__}"
        )
    return data


def _validate_list(model_cls, records: list[dict], filename: str) -> list:
    """Validate each record against a Pydantic model; raise CatalogValidationError on failure."""
    results = []
    for i, record in enumerate(records):
        try:
            results.append(model_cls.model_validate(record))
        except ValidationError as exc:
            raise CatalogValidationError(
                f"Validation error in {filename}[{i}]: {exc}"
            ) from exc
    return results


def load_catalog(data_dir: Path | None = None) -> dict[str, list]:
    """
    Load and validate all catalog data files.

    Returns a dict with keys:
      "cruises", "itineraries", "dining", "land", "staterooms"

    Raises CatalogValidationError if any file is missing, malformed, or fails
    Pydantic validation.
    """
    global _catalog
    _dir = data_dir or _DATA_DIR

    def _load(filename: str) -> list[dict]:
        path = _dir / filename
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CatalogValidationError(f"Catalog file not found: {path}")
        except json.JSONDecodeError as exc:
            raise CatalogValidationError(f"Invalid JSON in {filename}: {exc}")
        if not isinstance(data, list):
            raise CatalogValidationError(
                f"{filename} must be a JSON array, got {type(data).__name__}"
            )
        return data

    cruises = _validate_list(Cruise, _load("cruises.json"), "cruises.json")
    itineraries = _validate_list(ItineraryDay, _load("itineraries.json"), "itineraries.json")
    dining = _validate_list(DiningVenue, _load("dining.json"), "dining.json")
    land = _validate_list(LandOption, _load("land_options.json"), "land_options.json")
    staterooms = _validate_list(StateroomCategory, _load("staterooms.json"), "staterooms.json")

    _catalog = {
        "cruises": cruises,
        "itineraries": itineraries,
        "dining": dining,
        "land": land,
        "staterooms": staterooms,
    }
    return _catalog


def get_catalog() -> dict[str, list]:
    """Return the loaded catalog, loading it first if necessary."""
    global _catalog
    if _catalog is None:
        _catalog = load_catalog()
    return _catalog
