from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "config" / "stations.yaml"


def _normalise(value: object) -> str:
    return "" if value is None else " ".join(str(value).strip().lower().split())


def _empty_registry() -> dict[str, Any]:
    return {"version": 1, "source": {}, "stations": {}, "counties": {}}


def load_station_registry(path: str | Path | None = None) -> dict[str, Any]:
    """Load the public station registry without making the dashboard depend on it."""
    registry_path = Path(path) if path is not None else DEFAULT_REGISTRY_PATH
    try:
        payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return _empty_registry()
    if not isinstance(payload, Mapping):
        return _empty_registry()
    stations = payload.get("stations", {})
    counties = payload.get("counties", {})
    if not isinstance(stations, Mapping) or not isinstance(counties, Mapping):
        return _empty_registry()
    return {
        "version": payload.get("version", 1),
        "source": dict(payload.get("source", {})) if isinstance(payload.get("source", {}), Mapping) else {},
        "stations": {str(key): dict(value) for key, value in stations.items() if isinstance(value, Mapping)},
        "counties": {str(key): dict(value) for key, value in counties.items() if isinstance(value, Mapping)},
    }


def _sections(registry: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    stations = registry.get("stations", registry)
    counties = registry.get("counties", {})
    return (
        stations if isinstance(stations, Mapping) else {},
        counties if isinstance(counties, Mapping) else {},
    )


def _matches(value: object, canonical: str, metadata: Mapping[str, Any]) -> bool:
    target = _normalise(value)
    candidates = [canonical, *(metadata.get("aliases", []) if isinstance(metadata.get("aliases", []), list) else [])]
    return target in {_normalise(candidate) for candidate in candidates}


def lookup_station(
    site_name: str,
    county: str | None = None,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    loaded = registry if registry is not None else load_station_registry()
    stations, _ = _sections(loaded)
    for canonical, metadata in stations.items():
        if not isinstance(metadata, Mapping) or not _matches(site_name, str(canonical), metadata):
            continue
        if county and metadata.get("county") and _normalise(metadata.get("county")) != _normalise(county):
            aliases = metadata.get("county_aliases", [])
            if _normalise(county) not in {_normalise(alias) for alias in aliases if isinstance(aliases, list)}:
                continue
        result = dict(metadata)
        result["site_name"] = str(canonical)
        result.setdefault("coordinate_source", "unknown")
        result.setdefault("source_note", "No coordinate provenance note provided.")
        return result
    return None

def get_station_location(
    site_name: str,
    county: str | None = None,
    registry: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return coordinates plus provenance; county fallback is explicitly approximate."""
    loaded = registry if registry is not None else load_station_registry()
    station = lookup_station(site_name, county, loaded)
    if station is not None and station.get("latitude") is not None and station.get("longitude") is not None:
        return station

    _, counties = _sections(loaded)
    for canonical, metadata in counties.items():
        if _matches(county, str(canonical), metadata):
            return {
                "site_name": str(site_name),
                "county": str(canonical),
                "latitude": metadata.get("latitude"),
                "longitude": metadata.get("longitude"),
                "coordinate_source": "approximate_county_centroid",
                "source_note": "Approximate county centroid; not the exact monitoring station location.",
            }
    return None
