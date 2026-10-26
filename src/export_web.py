"""Run the analytics on cleaned observations and export JSON for the web app.

Deterministic by construction: no wall-clock time, sorted collections and
rounded floats, so the same inputs always produce byte-identical files.

Usage: python -m src.export_web [--out web/public/data]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.analytics import aqi_scale, attribution, drift, forecast, planner, propagation, whatif
from src.analytics.panel import build_panels
from src.station_registry import get_station_location
from src.utils import load_config, project_path, resolve_path

SCHEMA_VERSION = "2.0"
DEFAULT_OUT = Path("web/public/data")
HISTORY_HOURS = 72
EVENT_CONTEXT_HOURS = 12


def _num(value: Any, digits: int = 1) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _iso(ts: pd.Timestamp) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M")


def _write_json(path: Path, payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text(text + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _station_meta(cleaned: pd.DataFrame) -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    grid_coordinates: dict[str, dict[str, Any]] = {}
    if {"latitude", "longitude"}.issubset(cleaned.columns):
        columns = ["site_name", "latitude", "longitude"]
        if "coordinate_source" in cleaned.columns:
            columns.append("coordinate_source")
        rows = cleaned[columns].dropna(subset=["latitude", "longitude"]).drop_duplicates("site_name", keep="last")
        for row in rows.to_dict(orient="records"):
            grid_coordinates[str(row["site_name"])] = {
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "coordinate_source": row.get("coordinate_source", "unknown"),
            }
    for station, county in cleaned[["site_name", "county"]].drop_duplicates().itertuples(index=False):
        location = grid_coordinates.get(station) or get_station_location(station, county) or {}
        meta[station] = {
            "county": county,
            "latitude": _num(location.get("latitude"), 3),
            "longitude": _num(location.get("longitude"), 3),
            "coordinate_source": location.get("coordinate_source", "unknown"),
        }
    return meta



def build_overview(panels: dict[str, pd.DataFrame], meta: dict[str, dict[str, Any]], forecasts: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    aqi = panels["aqi"]
    latest_time = aqi.index[-1]
    stations = []
    for station in aqi.columns:
        recent = aqi[station].iloc[-HISTORY_HOURS:]
        current = aqi[station].iloc[-1]
        key, label = aqi_scale.category(float(current))
        stations.append(
            {
                "station": station,
                **meta[station],
                "aqi": _num(current),
                "pm25": _num(panels["pm25"][station].iloc[-1]),
                "pm10": _num(panels["pm10"][station].iloc[-1]),
                "o3": _num(panels["o3"][station].iloc[-1]),
                "wind_speed": _num(panels["wind_speed"][station].iloc[-1], 2),
                "category": key,
                "category_label": label,
                "history": [{"t": _iso(t), "aqi": _num(v)} for t, v in recent.items()],
                "forecast": forecasts.get(station, []),
            }
        )
    return {
        "latest": _iso(latest_time),
        "stations": stations,
        "categories": [{"upper": upper, "key": key, "label": label} for upper, key, label in aqi_scale.CATEGORIES],
        "planner_thresholds": planner.THRESHOLDS,
    }


def build_propagation(panels: dict[str, pd.DataFrame], truth_lags: dict[str, int] | None) -> tuple[dict[str, Any], dict[str, str]]:
    links, matrix = propagation.lead_lag_links(panels["pm25"])
    upstream = propagation.nearest_upstream(links)
    chain = sorted({l.upstream for l in links} | {l.downstream for l in links})
    start, end = propagation.strongest_episode(panels["pm25"], chain or list(panels["pm25"].columns))
    window = panels["aqi"].loc[start:end]
    payload = {
        "max_lag": propagation.MAX_LAG,
        "min_correlation": propagation.MIN_CORRELATION,
        "links": [
            {
                "upstream": l.upstream,
                "downstream": l.downstream,
                "lag_hours": l.lag_hours,
                "r": l.correlation,
                "r_synchronous": l.synchronous_correlation,
                "truth_lag": (truth_lags[l.downstream] - truth_lags[l.upstream]) if truth_lags and l.upstream in truth_lags and l.downstream in truth_lags else None,
            }
            for l in links
        ],
        "nearest_upstream": {station: {"upstream": l.upstream, "lag_hours": l.lag_hours} for station, l in sorted(upstream.items())},
        "matrix": matrix,
        "episode": {
            "start": _iso(start),
            "end": _iso(end),
            "times": [_iso(t) for t in window.index],
            "aqi": {station: [_num(v) for v in window[station]] for station in window.columns},
        },
        "ground_truth": truth_lags,
    }
    return payload, {station: link.upstream for station, link in upstream.items()}


def build_anomalies(panels: dict[str, pd.DataFrame], regional_window: int, truth: pd.DataFrame | None) -> dict[str, Any]:
    events = attribution.detect_events(panels, regional_window_hours=regional_window)
    baseline = panels["pm25"].groupby(panels["pm25"].index.hour).median()
    rows = []
    for event in events:
        context = panels["pm25"][event.station].loc[event.start - pd.Timedelta(hours=EVENT_CONTEXT_HOURS) : event.end + pd.Timedelta(hours=EVENT_CONTEXT_HOURS)]
        rows.append(
            {
                "id": event.event_id,
                "station": event.station,
                "start": _iso(event.start),
                "end": _iso(event.end),
                "peak": _iso(event.peak),
                "duration_hours": event.duration_hours,
                "peak_aqi": _num(event.peak_aqi),
                "peak_pm25": _num(event.peak_pm25),
                "kind": event.kind,
                "drivers": event.drivers(),
                "similar": event.similar,
                "context": [
                    {"t": _iso(t), "pm25": _num(v), "baseline": _num(baseline.at[t.hour, event.station])}
                    for t, v in context.items()
                ],
            }
        )
    validation = None
    if truth is not None and not truth.empty:
        slack = pd.Timedelta(hours=1)

        def matches(event: attribution.Event) -> bool:
            return any(
                event.station == r.site_name and event.start <= pd.Timestamp(r.end) + slack and event.end >= pd.Timestamp(r.start) - slack
                for r in truth.itertuples(index=False)
            )

        local = [e for e in events if e.kind == "local"]
        validation = {
            "injected_events": int(len(truth)),
            "recall": _num(attribution.recall(events, truth), 3),
            "local_events": len(local),
            "local_precision": _num(sum(matches(e) for e in local) / len(local), 3) if local else None,
            "injected_labelled_regional": int(sum(matches(e) for e in events if e.kind == "regional")),
        }
    return {
        "threshold": attribution.Z_THRESHOLD,
        "regional_window_hours": regional_window,
        "variables": attribution.VARIABLE_LABELS,
        "events": rows,
        "validation": validation,
    }


def build_model(base: forecast.ForecastResult, enhanced: forecast.ForecastResult, downstream: list[str], panels: dict[str, pd.DataFrame]) -> dict[str, Any]:
    horizons = []
    for b, e in zip(base.horizons, enhanced.horizons):
        horizons.append(
            {
                "h": e.horizon,
                "coverage": _num(e.test_coverage, 3),
                "mae": _num(e.test_mae, 2),
                "mae_without_upstream": _num(b.test_mae, 2),
                "persistence_mae": _num(e.persistence_mae, 2),
                "climatology_mae": _num(e.climatology_mae, 2),
                "downstream_mae": _num(np.mean([e.station_mae[s] for s in downstream]), 2) if downstream else None,
                "downstream_mae_without_upstream": _num(np.mean([b.station_mae[s] for s in downstream]), 2) if downstream else None,
                "interval": [_num(q, 1) for q in e.residual_quantiles],
                "test_size": e.test_size,
            }
        )
    return {
        "split": enhanced.split,
        "features": enhanced.features,
        "target_coverage": 0.8,
        "preprocessing": "causal forward fill up to 3 hours; upstream topology selected on training interval only",
        "horizons": horizons,
        "downstream_stations": downstream,
        "drift": drift.mean_shift(panels["pm25"]),
    }


def _resolution_hours(value: Any, default: int = 1) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if isinstance(value, bool) or not 1 <= parsed <= 24:
        return default
    return parsed


def build_provenance(cleaned: pd.DataFrame, config: dict[str, Any], sample_dir: Path) -> dict[str, Any]:
    metadata_path = resolve_path(config, "reports.source_metadata_file")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    frame = cleaned.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    provider = str(metadata.get("provider") or "unknown")
    modelled = provider == "open_meteo_cams_global" and metadata.get("is_simulated_data") is False
    native_resolution = _resolution_hours(metadata.get("native_temporal_resolution_hours"), 3 if modelled else 1)
    api_resolution = _resolution_hours(metadata.get("api_output_temporal_resolution_hours"), 1)
    expected = 0
    for _, station_rows in frame.groupby("site_name"):
        first, last = station_rows["datetime"].min(), station_rows["datetime"].max()
        expected += int((last - first) / pd.Timedelta(hours=api_resolution)) + 1
    sources = (
        [
            {"label": "Open-Meteo Air Quality API · CAMS Global", "url": "https://open-meteo.com/en/docs/air-quality-api"},
            {"label": "CAMS Global Atmospheric Composition Forecasts · Copernicus Atmosphere Monitoring Service", "url": "https://atmosphere.copernicus.eu/"},
            {"label": "Open-Meteo Forecast API (wind fields)", "url": "https://open-meteo.com/en/docs"},
        ]
        if modelled
        else [
            {"label": "環境部空氣品質指標（AQX_P_432）", "url": "https://data.moenv.gov.tw/dataset/detail/aqx_p_432"},
            {"label": "環境部 AQI 分級說明", "url": "https://airtw.moenv.gov.tw/"},
        ]
    )
    source_rows = metadata.get("row_count") if modelled else len(frame)
    if not isinstance(source_rows, int) or isinstance(source_rows, bool) or source_rows < 0:
        source_rows = len(frame)
    return {
        "data_source": "Open-Meteo CAMS Global model estimates" if modelled else metadata.get("data_source", "Unknown"),
        "is_simulated": bool(metadata.get("is_simulated_data", True)),
        "is_model_estimate": modelled,
        "provider": provider,
        "model_name": metadata.get("model_name") if modelled else None,
        "aqi_standard": metadata.get("aqi_standard") if modelled else "Taiwan AQI",
        "native_temporal_resolution_hours": native_resolution,
        "api_output_temporal_resolution_hours": api_resolution if modelled else None,
        "spatial_resolution_km": metadata.get("spatial_resolution_km") if modelled else None,
        "timezone": metadata.get("timezone", "Asia/Taipei"),
        "ozone_unit": metadata.get("ozone_unit", "ppb"),
        "interpolation": metadata.get("interpolation") if modelled else None,
        "seed": config.get("random_state"),
        "range": {"start": _iso(frame["datetime"].min()), "end": _iso(frame["datetime"].max())},
        "stations": int(frame["site_name"].nunique()),
        "rows": int(source_rows),
        "completeness": _num(source_rows / expected, 4) if expected else None,
        "input_sha256": metadata.get("data_file_sha256"),
        "schema_sha256": metadata.get("schema_sha256"),
        "injected_events_file": "data/sample/injected_events.csv" if not modelled and bool(metadata.get("is_simulated_data", True)) and (sample_dir / "injected_events.csv").exists() else None,
        "sources": sources,
    }



MIN_HISTORY_DAYS = 14


class InsufficientHistoryError(ValueError):
    """Raised when the input is too short to train and test the models honestly."""



def training_upstream(panels: dict[str, pd.DataFrame]) -> dict[str, str]:
    """Select predictive topology using the training interval only."""
    train_end, _ = forecast.split_times(panels["aqi"].index)
    links, _ = propagation.lead_lag_links(panels["pm25"].loc[:train_end])
    return {station: link.upstream for station, link in propagation.nearest_upstream(links).items()}


def export(out_dir: Path, cleaned_path: Path | None = None) -> dict[str, str]:
    config = load_config()
    cleaned_file = cleaned_path or resolve_path(config, "data.cleaned_file")
    cleaned = pd.read_csv(cleaned_file)
    panels = build_panels(cleaned, causal=True)
    span = panels["aqi"].index[-1] - panels["aqi"].index[0] if len(panels["aqi"].index) else pd.Timedelta(0)
    if span < pd.Timedelta(days=MIN_HISTORY_DAYS):
        raise InsufficientHistoryError(
            f"Need at least {MIN_HISTORY_DAYS} days of hourly history to train, calibrate and test the models; "
            f"got {span}. The live API returns only the latest hour, so archive snapshots first or use --mode sample."
        )
    sample_dir = resolve_path(config, "data.sample_file").parent
    simulated = (cleaned.get("data_source", pd.Series(["Sample Data"])) == "Sample Data").all()
    truth_path = sample_dir / "injected_events.csv"
    truth = pd.read_csv(truth_path) if simulated and truth_path.exists() else None
    truth_lags = None
    if simulated:
        from src.generate_sample_data import TRANSPORT_LAG_HOURS

        truth_lags = dict(TRANSPORT_LAG_HOURS)

    propagation_payload, _display_upstream = build_propagation(panels, truth_lags)
    upstream = training_upstream(panels)
    provenance_payload = build_provenance(cleaned, config, sample_dir)
    regional_window = max([l["lag_hours"] for l in propagation_payload["links"]], default=attribution.REGIONAL_WINDOW_HOURS)
    base = forecast.fit_forecaster(panels)
    enhanced = forecast.fit_forecaster(panels, upstream=upstream)
    _, whatif_payload = whatif.fit_whatif(panels, ozone_unit=str(provenance_payload["ozone_unit"]))
    meta = _station_meta(cleaned)

    files = {
        "overview.json": build_overview(panels, meta, enhanced.forecasts),
        "propagation.json": propagation_payload,
        "anomalies.json": build_anomalies(panels, regional_window, truth),
        "whatif.json": whatif_payload,
        "model.json": build_model(base, enhanced, sorted(upstream), panels),
        "provenance.json": provenance_payload,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    hashes = {name: _write_json(out_dir / name, payload) for name, payload in files.items()}
    _write_json(out_dir / "manifest.json", {"schema_version": SCHEMA_VERSION, "files": hashes})
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.out if args.out.is_absolute() else project_path(str(args.out))
    for name, digest in export(out).items():
        print(f"{name} {digest}")


if __name__ == "__main__":
    main()
