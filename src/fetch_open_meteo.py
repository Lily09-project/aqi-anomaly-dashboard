"""Fetch public Open-Meteo CAMS global model estimates for Taiwan.

CAMS Global is native three-hourly data on roughly 45 km grid cells. Open-Meteo
returns hourly time steps from this model; intermediate values are provider
interpolation, not new observations or station measurements.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import pandas as pd

try:
    import requests
except Exception:
    requests = None

from src.source_metadata import build_source_metadata, file_sha256, frame_summary, write_source_metadata
from src.utils import load_config, resolve_path, write_csv

PROVIDER = "open_meteo_cams_global"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
TAIPEI = ZoneInfo("Asia/Taipei")
MAX_BYTES = 12 * 1024 * 1024
LOCATIONS = (
    {"site_name": "臺北網格", "county": "Taipei City", "latitude": 25.037, "longitude": 121.564},
    {"site_name": "臺中網格", "county": "Taichung City", "latitude": 24.147, "longitude": 120.673},
    {"site_name": "高雄網格", "county": "Kaohsiung City", "latitude": 22.627, "longitude": 120.301},
    {"site_name": "花蓮網格", "county": "Hualien County", "latitude": 23.987, "longitude": 121.601},
)
AIR_FIELDS = ("us_aqi", "pm2_5", "pm10", "ozone", "carbon_monoxide")
WEATHER_FIELDS = ("wind_speed_10m", "wind_direction_10m")
API_STEP = pd.Timedelta(hours=1)
# Missing (null) values are tolerated only where downstream gap handling can
# absorb them: preprocess forward-fills at most 3 consecutive hours and
# build_panels interpolates interior gaps of at most 3 hours (GAP_FILL_HOURS).
# Trailing hours where any field is null are trimmed instead, subject to the
# existing 48-hour staleness and minimum-history checks. Longer runs, or more
# than 2% nulls in any field of one region (~29 h of a 60-day window), fail
# closed. Non-null values that are not finite numbers always fail.
MAX_NULL_RUN_HOURS = 3
MAX_NULL_SHARE = 0.02
COLUMN_FIELDS = (
    ("aqi", "us_aqi"), ("pm25", "pm2_5"), ("pm10", "pm10"), ("o3", "ozone"), ("co", "carbon_monoxide"),
    ("wind_speed", "wind_speed_10m"), ("wind_directions", "wind_direction_10m"),
)
VALUE_RANGES = {
    "aqi": (0, 1000), "pm25": (0, math.inf), "pm10": (0, math.inf), "o3": (0, math.inf), "co": (0, math.inf),
    "wind_speed": (0, 200), "wind_directions": (0, 360),
}


def _metadata_path(config: Mapping[str, Any], target: str | Path | None) -> Path:
    return Path(target) if target is not None else resolve_path(dict(config), "reports.source_metadata_file")


def _get_json(client: Any, url: str, params: dict[str, Any]) -> Any:
    response = client.get(url, params=params, timeout=(5, 40), stream=True, allow_redirects=False)
    try:
        if 300 <= int(getattr(response, "status_code", 0)) < 400:
            raise ValueError("redirects are not allowed")
        actual, expected = urlsplit(str(getattr(response, "url", url))), urlsplit(url)
        if actual.scheme != "https" or actual.hostname != expected.hostname or actual.port not in (None, 443):
            raise ValueError("upstream response origin is not allowed")
        headers = getattr(response, "headers", {}) or {}
        size = headers.get("content-length")
        if size and int(size) > MAX_BYTES:
            raise ValueError("response is too large")
        response.raise_for_status()
        chunks, total = [], 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if chunk:
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("response is too large")
                chunks.append(chunk)
        return json.loads(b"".join(chunks).decode("utf-8"))
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def _location_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        values = [payload] if len(LOCATIONS) == 1 else None
    else:
        values = payload if isinstance(payload, list) else None
    if values is None or len(values) != len(LOCATIONS) or not all(isinstance(v, dict) for v in values):
        raise ValueError("unexpected location response")
    return values


def _hourly(item: Mapping[str, Any], fields: tuple[str, ...]) -> tuple[list[pd.Timestamp], dict[str, list[Any]]]:
    data = item.get("hourly")
    if not isinstance(data, dict) or not isinstance(data.get("time"), list) or not data["time"]:
        raise ValueError("hourly source data is missing")
    times = []
    for value in data["time"]:
        stamp = pd.Timestamp(value)
        times.append(stamp.tz_localize(TAIPEI) if stamp.tzinfo is None else stamp.tz_convert(TAIPEI))
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("timestamps are duplicated or unordered")
    arrays = {}
    for field in fields:
        value = data.get(field)
        if not isinstance(value, list) or len(value) != len(times):
            raise ValueError("hourly source variable is missing or misaligned")
        arrays[field] = value
    return times, arrays


def _number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"invalid {field}: booleans are not measurements")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}") from exc
    if not math.isfinite(result):
        raise ValueError(f"non-finite {field}")
    return result


def _nullable_number(value: Any, field: str) -> float:
    """Map an explicit JSON null to NaN; every other value must be a finite number."""
    return math.nan if value is None else _number(value, field)


def _longest_null_run(values: pd.Series) -> int:
    missing = values.isna()
    if not missing.any():
        return 0
    return int(missing.groupby((~missing).cumsum()).sum().max())


def _write_failure(target: Path, requested: str, exc: Exception) -> None:
    metadata = build_source_metadata(
        provider=PROVIDER, mode="api", status="fallback", source_url=AIR_URL,
        requested_at_utc=requested, fallback_reason="open_meteo_request_or_validation_failed",
        error_type=type(exc).__name__,
    )
    metadata["timezone"] = "Asia/Taipei"
    write_source_metadata(target, metadata)


def fetch_open_meteo(
    config: dict[str, Any] | None = None,
    output_path: str | Path | None = None,
    metadata_path: str | Path | None = None,
    *,
    client: Any = None,
    now: datetime | None = None,
) -> Path | None:
    cfg = config or load_config()
    api = cfg.get("api", {})
    metadata_target = _metadata_path(cfg, metadata_path)
    current = now or datetime.now(timezone.utc)
    current_taipei = current.astimezone(TAIPEI) if current.tzinfo else current.replace(tzinfo=TAIPEI)
    requested = current_taipei.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    try:
        past_days, minimum_days = int(api.get("past_days", 60)), int(api.get("minimum_history_days", 30))
        if not 30 <= past_days <= 92 or not 14 <= minimum_days <= past_days:
            raise ValueError("invalid history window")
        http = client or requests
        if http is None:
            raise RuntimeError("requests is not installed")
        lat = ",".join(str(x["latitude"]) for x in LOCATIONS)
        lon = ",".join(str(x["longitude"]) for x in LOCATIONS)
        shared = {"latitude": lat, "longitude": lon, "past_days": past_days, "forecast_days": 0,
                  "timezone": "Asia/Taipei", "cell_selection": "nearest"}
        air = _location_list(_get_json(http, AIR_URL, {**shared, "hourly": ",".join(AIR_FIELDS), "domains": "cams_global"}))
        weather = _location_list(_get_json(http, WEATHER_URL, {**shared, "hourly": ",".join(WEATHER_FIELDS), "wind_speed_unit": "ms"}))
        grid_cells: set[tuple[float, float]] = set()
        frames = []
        missing_report: list[dict[str, Any]] = []
        minimum_span = pd.Timedelta(days=minimum_days)
        for config_location, aqi_location, weather_location in zip(LOCATIONS, air, weather):
            grid_lat = _number(aqi_location.get("latitude"), "grid latitude")
            grid_lon = _number(aqi_location.get("longitude"), "grid longitude")
            if not (21 <= grid_lat <= 26.8 and 118.5 <= grid_lon <= 123.5):
                raise ValueError("CAMS returned a grid outside Taiwan")
            if abs(grid_lat-config_location["latitude"]) > .6 or abs(grid_lon-config_location["longitude"]) > .6:
                raise ValueError("CAMS grid is too far from the requested region")
            cell = (round(grid_lat, 3), round(grid_lon, 3))
            if cell in grid_cells:
                raise ValueError("requested regions resolve to the same CAMS grid cell")
            grid_cells.add(cell)
            air_times, air_values = _hourly(aqi_location, AIR_FIELDS)
            wind_times, wind_values = _hourly(weather_location, WEATHER_FIELDS)
            if air_times != wind_times:
                raise ValueError("air-quality and weather timelines are not exactly aligned")
            intervals = pd.Series(air_times).diff().dropna()
            if intervals.empty or not intervals.eq(API_STEP).all():
                raise ValueError("Open-Meteo hourly output is not a continuous one-hour series")
            if air_times[-1] > current_taipei:
                raise ValueError("CAMS history includes future data")
            hourly = {**air_values, **wind_values}
            values = pd.DataFrame({
                column: [_nullable_number(v, field) for v in hourly[field]]
                for column, field in COLUMN_FIELDS
            })
            complete = values.notna().all(axis=1)
            keep = int(complete[::-1].idxmax()) + 1 if complete.any() else 0
            trimmed = len(values) - keep
            values = values.iloc[:keep]
            times = air_times[:keep]
            if not times or current_taipei-times[-1] > pd.Timedelta(hours=48) or times[-1]-times[0] < minimum_span:
                raise ValueError("CAMS history is stale or too short after trimming trailing missing hours")
            masked = {}
            for column, field in COLUMN_FIELDS:
                count = int(values[column].isna().sum())
                if _longest_null_run(values[column]) > MAX_NULL_RUN_HOURS or count > MAX_NULL_SHARE * len(values):
                    raise ValueError(f"{field} has too many or too long missing runs")
                if count:
                    masked[field] = count
            for column, (low, high) in VALUE_RANGES.items():
                if ((values[column] < low) | (values[column] > high)).any():
                    raise ValueError("physically invalid source value")
            missing_report.append({"name": config_location["site_name"], "trimmed_trailing_hours": trimmed, "masked_values": masked})
            frame = values.assign(
                datetime=[stamp.isoformat(timespec="minutes") for stamp in times], site_name=config_location["site_name"],
                county=config_location["county"], latitude=grid_lat, longitude=grid_lon,
                coordinate_source="Open-Meteo snapped CAMS global grid",
            )[["datetime", "site_name", "county", *VALUE_RANGES, "latitude", "longitude", "coordinate_source"]]
            if frame.empty or len(frame) < minimum_days * 24 * .8:
                raise ValueError("too few aligned air-quality and weather rows")
            frames.append(frame)
        if len(grid_cells) != len(LOCATIONS):
            raise ValueError("incomplete CAMS region coverage")
        combined = pd.concat(frames, ignore_index=True)
        if combined.duplicated(["site_name", "datetime"]).any():
            raise ValueError("duplicate region timestamps")
        target = Path(output_path) if output_path is not None else resolve_path(cfg, "data.raw_dir") / "aqi_open_meteo.csv"
        write_csv(combined, target, index=False, encoding="utf-8")
        summary = frame_summary(combined)
        metadata = build_source_metadata(
            provider=PROVIDER, mode="api", status="success", data_source="Model Estimate",
            is_simulated_data=False, row_count=summary["row_count"], datetime_range=summary["datetime_range"],
            schema_columns=summary["schema_columns"], schema_hash=summary["schema_sha256"],
            source_url=AIR_URL, requested_at_utc=requested, fetched_at_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            data_file_sha256=file_sha256(target),
        )
        metadata.update({
            "timezone": "Asia/Taipei", "native_temporal_resolution_hours": 3, "api_output_temporal_resolution_hours": 1, "spatial_resolution_km": 45,
            "aqi_standard": "U.S. EPA AQI", "ozone_unit": "μg/m³", "carbon_monoxide_unit": "μg/m³",
            "wind_speed_unit": "ms", "model_name": "CAMS Global Atmospheric Composition Forecasts",
            "weather_model": "Open-Meteo Forecast API",
            "interpolation": "Open-Meteo returns an hourly series from native three-hourly CAMS data; intermediate hourly values are provider interpolation and are not additional observations.",
            "regions": [{"name": loc["site_name"], "latitude": round(float(item["latitude"]),3), "longitude": round(float(item["longitude"]),3)}
                        for loc, item in zip(LOCATIONS, air)],
            "missing_values": {
                "policy": f"Trailing hours with any null field are trimmed; up to {MAX_NULL_RUN_HOURS} consecutive null hours "
                          f"and at most {MAX_NULL_SHARE:.0%} nulls per field and region are kept as blanks for downstream short-gap filling.",
                "max_null_run_hours": MAX_NULL_RUN_HOURS, "max_null_share": MAX_NULL_SHARE, "regions": missing_report,
            },
        })
        write_source_metadata(metadata_target, metadata)
        return target
    except Exception as exc:
        _write_failure(metadata_target, requested, exc)
        detail = " ".join(str(exc).split())[:180] or "validation failed"
        print(f"Open-Meteo data unavailable or invalid; no model snapshot published: {type(exc).__name__}: {detail}")
        return None
