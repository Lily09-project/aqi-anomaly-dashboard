from __future__ import annotations

from pathlib import Path

from src.station_registry import get_station_location, load_station_registry, lookup_station


ROOT = Path(__file__).resolve().parents[1]


def test_registry_loads_public_source_contract() -> None:
    registry = load_station_registry(ROOT / "config" / "stations.yaml")

    assert registry["source"]["dataset_id"] == "AQX_P_07"
    assert "松山測站" in registry["stations"]
    assert registry["stations"]["松山測站"]["coordinate_source"] == "approximate_sample_coordinate"


def test_station_exact_match_and_alias_are_traceable() -> None:
    registry = load_station_registry()

    exact = lookup_station("松山測站", registry=registry)
    alias = lookup_station("Songshan", registry=registry)

    assert exact is not None
    assert exact["site_name"] == "松山測站"
    assert alias is not None
    assert alias["site_name"] == "松山測站"
    assert alias["coordinate_source"] == "approximate_sample_coordinate"


def test_unknown_station_uses_explicit_county_centroid_fallback() -> None:
    location = get_station_location("未知站", "臺北市")

    assert location is not None
    assert location["latitude"] == 25.033
    assert location["longitude"] == 121.565
    assert location["coordinate_source"] == "approximate_county_centroid"
    assert "exact" in location["source_note"]


def test_missing_registry_is_safe(tmp_path: Path) -> None:
    assert load_station_registry(tmp_path / "missing.yaml")["stations"] == {}
