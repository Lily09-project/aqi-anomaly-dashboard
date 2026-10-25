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
    meta = {}
    for station, county in cleaned[["site_name", "county"]].drop_duplicates().itertuples(index=False):
        location = get_station_location(station, county) or {}
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
        "horizons": horizons,
        "downstream_stations": downstream,
        "drift": drift.mean_shift(panels["pm25"]),
    }


def build_provenance(cleaned: pd.DataFrame, config: dict[str, Any], sample_dir: Path) -> dict[str, Any]:
    metadata_path = resolve_path(config, "reports.source_metadata_file")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    frame = cleaned.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    expected = frame["site_name"].nunique() * (int((frame["datetime"].max() - frame["datetime"].min()) / pd.Timedelta(hours=1)) + 1)
    return {
        "data_source": metadata.get("data_source", "Unknown"),
        "is_simulated": bool(metadata.get("is_simulated_data", True)),
        "provider": metadata.get("provider"),
        "seed": config.get("random_state"),
        "range": {"start": _iso(frame["datetime"].min()), "end": _iso(frame["datetime"].max())},
        "stations": int(frame["site_name"].nunique()),
        "rows": int(len(frame)),
        "completeness": _num(len(frame) / expected, 4) if expected else None,
        "input_sha256": metadata.get("data_file_sha256"),
        "schema_sha256": metadata.get("schema_sha256"),
        "injected_events_file": "data/sample/injected_events.csv" if (sample_dir / "injected_events.csv").exists() else None,
        "sources": [
            {"label": "環境部空氣品質指標（AQX_P_432）", "url": "https://data.moenv.gov.tw/dataset/detail/aqx_p_432"},
            {"label": "環境部 AQI 分級說明", "url": "https://airtw.moenv.gov.tw/"},
        ],
    }


MIN_HISTORY_DAYS = 14


class InsufficientHistoryError(ValueError):
    """Raised when the input is too short to train and test the models honestly."""


def export(out_dir: Path, cleaned_path: Path | None = None) -> dict[str, str]:
    config = load_config()
    cleaned_file = cleaned_path or resolve_path(config, "data.cleaned_file")
    cleaned = pd.read_csv(cleaned_file)
    panels = build_panels(cleaned)
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

    propagation_payload, upstream = build_propagation(panels, truth_lags)
    regional_window = max([l["lag_hours"] for l in propagation_payload["links"]], default=attribution.REGIONAL_WINDOW_HOURS)
    base = forecast.fit_forecaster(panels)
    enhanced = forecast.fit_forecaster(panels, upstream=upstream)
    _, whatif_payload = whatif.fit_whatif(panels)
    meta = _station_meta(cleaned)

    files = {
        "overview.json": build_overview(panels, meta, enhanced.forecasts),
        "propagation.json": propagation_payload,
        "anomalies.json": build_anomalies(panels, regional_window, truth),
        "whatif.json": whatif_payload,
        "model.json": build_model(base, enhanced, sorted(upstream), panels),
        "provenance.json": build_provenance(cleaned, config, sample_dir),
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
