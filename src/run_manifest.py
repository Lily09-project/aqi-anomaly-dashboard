from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.source_metadata import redact_source_url
from src.utils import write_json


MANIFEST_VERSION = "1.0"
MANIFEST_RELATIVE_PATH = Path("reports/metrics/run_manifest.json")
DEFAULT_METRIC_FILES = (
    "predictor_metrics.json",
    "anomaly_metrics.json",
    "backtest_metrics.json",
    "forecast_confidence.json",
    "data_health.json",
    "monitoring.json",
    "evaluation_summary.json",
)
DEFAULT_FIGURE_FILES = (
    "aqi_trend.png",
    "prediction_vs_actual.png",
    "anomaly_cases.png",
)
FORBIDDEN_FEATURES = ("target_aqi", "target_next_hour_aqi", "future_aqi")
LEAKAGE_CONTROLS = (
    "Target is the same-station AQI one hour ahead.",
    "Lag and rolling features are computed within site_name groups.",
    "Rolling windows are shifted before aggregation so the current target is not included.",
    "Train, validation, and final test use chronological boundaries instead of random splitting.",
    "Final test rows are excluded from model selection and forecast interval calibration.",
    "Monitoring predictions use rolling-origin out-of-fold rows plus a separately marked final-test window.",
)


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str | None:
    file_path = Path(path)
    if not file_path.is_file():
        return None
    digest = hashlib.sha256()
    with file_path.open("rb") as file:
        while chunk := file.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _git_command(root: Path, *arguments: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def _git_metadata(root: Path) -> dict[str, Any]:
    revision = _git_command(root, "rev-parse", "--short=12", "HEAD")
    if revision is None:
        return {"revision": "unavailable", "dirty": None}
    status = _git_command(root, "status", "--porcelain")
    return {"revision": revision, "dirty": bool(status)}


def _normalise_timestamp(value: datetime | str | None) -> str:
    if value is None:
        timestamp = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        timestamp = value
    else:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _config_value(config: Mapping[str, Any], dotted_key: str, default: Any = None) -> Any:
    value: Any = config
    for key in dotted_key.split("."):
        if not isinstance(value, Mapping) or key not in value:
            return default
        value = value[key]
    return value


def _project_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return "<outside-project>"


def _project_relative(directory: str | Path, name: str) -> str:
    return (Path(directory) / name).as_posix()


def _artifact_paths(config: Mapping[str, Any]) -> list[str | Path]:
    paths: list[str | Path] = [
        _config_value(config, "data.sample_file", "data/sample/sample_aqi.csv"),
        _config_value(config, "data.cleaned_file", "data/processed/aqi_cleaned.csv"),
        _config_value(config, "data.features_file", "data/processed/aqi_features.csv"),
        _config_value(config, "data.predictions_file", "data/processed/aqi_predictions.csv"),
        _config_value(
            config,
            "data.monitoring_predictions_file",
            "data/processed/aqi_monitoring_predictions.csv",
        ),
        _config_value(config, "data.anomaly_file", "data/processed/aqi_anomaly_results.csv"),
        _config_value(config, "data.events_file", "data/processed/aqi_anomaly_events.csv"),
        _config_value(config, "reports.source_metadata_file", "reports/metrics/source_metadata.json"),
        _config_value(config, "models.predictor", "models/aqi_predictor.joblib"),
        _config_value(config, "models.anomaly_detector", "models/anomaly_detector.joblib"),
    ]
    metrics_dir = _config_value(config, "reports.metrics_dir", "reports/metrics")
    figures_dir = _config_value(config, "reports.figures_dir", "reports/figures")
    confidence_file = _config_value(config, "reports.confidence_file", f"{metrics_dir}/forecast_confidence.json")
    paths.extend(_project_relative(metrics_dir, name) for name in DEFAULT_METRIC_FILES if name != "forecast_confidence.json")
    paths.append(confidence_file)
    paths.extend(_project_relative(figures_dir, name) for name in DEFAULT_FIGURE_FILES)
    return list(dict.fromkeys(paths))


def _artifact_records(root: Path, paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in paths:
        path = _project_path(root, value)
        relative = _relative_path(root, path)
        if relative in seen or relative == "<outside-project>":
            continue
        seen.add(relative)
        exists = path.is_file()
        records.append(
            {
                "path": relative,
                "exists": exists,
                "size_bytes": path.stat().st_size if exists else None,
                "sha256": sha256_file(path),
            }
        )
    return records


def _compact_metrics(root: Path) -> dict[str, Any]:
    metrics_root = root / "reports" / "metrics"
    predictor = _read_json(metrics_root / "predictor_metrics.json")
    anomaly = _read_json(metrics_root / "anomaly_metrics.json")
    backtest = _read_json(metrics_root / "backtest_metrics.json")
    confidence = _read_json(metrics_root / "forecast_confidence.json")
    data_health = _read_json(metrics_root / "data_health.json")
    monitoring = _read_json(metrics_root / "monitoring.json")
    return {
        "predictor": {
            "best_model": predictor.get("best_model"),
            "mae": predictor.get("mae"),
            "rmse": predictor.get("rmse"),
            "r2": predictor.get("r2"),
            "selection_basis": predictor.get("selection_basis"),
            "split_rows": predictor.get("split_rows", {}),
        },
        "anomaly": {
            "precision": anomaly.get("precision"),
            "recall": anomaly.get("recall"),
            "f1": anomaly.get("f1"),
            "anomaly_count": anomaly.get("anomaly_count"),
            "event_count": anomaly.get("event_count"),
            "limitation_note": anomaly.get("limitation_note"),
        },
        "backtest": {
            "fold_count": backtest.get("fold_count"),
            "aggregate": backtest.get("aggregate", {}),
        },
        "forecast_confidence": {
            "method": confidence.get("method"),
            "calibration_rows": confidence.get("calibration_rows"),
            "final_test_period": confidence.get("final_test_period", {}),
            "intervals": confidence.get("intervals", {}),
            "limitation_note": confidence.get("limitation_note"),
        },
        "data_health": data_health,
        "monitoring": {
            "status": monitoring.get("status"),
            "reference_window": monitoring.get("reference_window", {}),
            "current_window": monitoring.get("current_window", {}),
            "prediction_status": monitoring.get("prediction", {}).get("status")
            if isinstance(monitoring.get("prediction"), dict)
            else None,
            "retraining_recommended": bool(
                monitoring.get("retraining", {}).get("recommended")
                if isinstance(monitoring.get("retraining"), dict)
                else False
            ),
            "reasons": monitoring.get("retraining", {}).get("reasons", [])
            if isinstance(monitoring.get("retraining"), dict)
            else [],
        },
    }



def _source_summary(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Allowlist provenance fields so arbitrary metadata never enters a manifest."""
    source = metadata if isinstance(metadata, Mapping) else {}
    datetime_range = source.get("datetime_range", {})
    datetime_range = dict(datetime_range) if isinstance(datetime_range, Mapping) else {}
    return {
        "metadata_version": source.get("metadata_version", "unknown"),
        "provider": source.get("provider", "unknown"),
        "mode": source.get("mode", "unknown"),
        "status": source.get("status", "unknown"),
        "data_source": source.get("data_source", "Unknown"),
        "is_simulated_data": bool(source.get("is_simulated_data", False)),
        "source_url": redact_source_url(str(source.get("source_url", ""))),
        "requested_at_utc": source.get("requested_at_utc"),
        "fetched_at_utc": source.get("fetched_at_utc"),
        "row_count": int(source.get("row_count", 0) or 0),
        "datetime_range": {"min": datetime_range.get("min"), "max": datetime_range.get("max")},
        "schema_columns": sorted(str(column) for column in source.get("schema_columns", []) if str(column)),
        "schema_sha256": source.get("schema_sha256"),
        "fallback_reason": source.get("fallback_reason"),
        "error_type": source.get("error_type"),
        "http_status": source.get("http_status"),
    }
def build_run_manifest(
    repo_root: str | Path,
    *,
    config: Mapping[str, Any],
    run_mode: str,
    artifacts: Iterable[str | Path] | None = None,
    generated_at: datetime | str | None = None,
    source_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    timestamp = _normalise_timestamp(generated_at)
    git = _git_metadata(root)
    revision = str(git["revision"])
    run_id = f"{timestamp.replace('-', '').replace(':', '')}-{revision}"
    feature_columns = list(_config_value(config, "train.feature_columns", []))
    forbidden_features_found = sorted(set(feature_columns).intersection(FORBIDDEN_FEATURES))
    evaluation_summary = _read_json(root / "reports" / "metrics" / "evaluation_summary.json")
    source_metadata_path = _project_path(root, _config_value(config, "reports.source_metadata_file", "reports/metrics/source_metadata.json"))
    disk_source_metadata = _read_json(source_metadata_path)
    provenance = _source_summary(source_metadata if source_metadata is not None else disk_source_metadata)
    has_provenance = source_metadata is not None or bool(disk_source_metadata)
    mode_label = provenance["data_source"] if has_provenance else ("Sample Data" if run_mode == "sample" else "API Data")
    simulated_data = bool(provenance["is_simulated_data"]) if has_provenance else run_mode == "sample"
    compact_metrics = _compact_metrics(root)
    artifact_values = _artifact_paths(config) if artifacts is None else list(artifacts)

    return {
        "manifest_version": MANIFEST_VERSION,
        "manifest_path": MANIFEST_RELATIVE_PATH.as_posix(),
        "run_id": run_id,
        "generated_at_utc": timestamp,
        "project": {
            "name": _config_value(config, "project.name", "AQI dashboard"),
            "git_revision": revision,
            "git_dirty": git["dirty"],
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "run": {
            "mode": run_mode,
            "data_source": mode_label,
            "is_simulated_data": simulated_data,
            "reproducible_sample": run_mode == "sample",
            "random_state": _config_value(config, "random_state"),
            "config": {"path": "config.yaml", "sha256": sha256_file(Path(root) / "config.yaml")},
            "requirements": {"path": "requirements.txt", "sha256": sha256_file(Path(root) / "requirements.txt")},
        },
        "data_contract": {
            "forecast_horizon": "next_hour",
            "target": "target_next_hour_aqi",
            "compatibility_alias": "target_aqi",
            "group_key": "site_name",
            "feature_columns": feature_columns,
            "forbidden_feature_columns": list(FORBIDDEN_FEATURES),
            "feature_contract_valid": not forbidden_features_found,
            "forbidden_features_found": forbidden_features_found,
            "split_strategy": "chronological train / validation / final_test",
            "leakage_controls": list(LEAKAGE_CONTROLS),
        },
        "source": provenance,
        "dataset_summary": {
            "rows": evaluation_summary.get("rows", {}),
            "station_count": evaluation_summary.get("site_count"),
            "datetime_range": evaluation_summary.get("datetime_range", {}),
            "data_health_status": compact_metrics["data_health"].get("status"),
        },
        "metrics": compact_metrics,
        "source_metadata_sha256": sha256_file(source_metadata_path),
        "artifacts": _artifact_records(root, artifact_values),
        "limitations": [
            "Sample Data is simulated and is intended only for local demonstration and testing.",
            "Anomaly metrics use pseudo-labels rather than verified pollution incident labels.",
            "Forecast intervals report empirical historical coverage and are not official alerts or guaranteed probabilities.",
            "Generated data, models, figures, and metrics are local outputs and are intentionally excluded from the public repository.",
        ],
    }


def write_run_manifest(
    repo_root: str | Path,
    *,
    config: Mapping[str, Any],
    run_mode: str,
    output_path: str | Path | None = None,
    source_metadata: Mapping[str, Any] | None = None,
) -> Path:
    root = Path(repo_root).resolve()
    target = Path(output_path) if output_path is not None else root / MANIFEST_RELATIVE_PATH
    if not target.is_absolute():
        target = root / target
    target = target.resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("Manifest output must stay inside the project root") from exc
    manifest = build_run_manifest(root, config=config, run_mode=run_mode, source_metadata=source_metadata)
    write_json(target, manifest)
    return target
