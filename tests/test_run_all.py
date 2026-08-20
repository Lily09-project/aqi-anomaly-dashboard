from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_all import run
from src.utils import load_config, resolve_path


def test_run_all_sample_creates_required_outputs():
    config = load_config()
    assert (ROOT / "run_all.py").exists()
    assert (ROOT / "run_project.bat").exists()
    assert (ROOT / "run_project_bat內容.txt").exists()
    assert (ROOT / "run_project.bat").read_text(encoding="utf-8") == (
        ROOT / "run_project_bat內容.txt"
    ).read_text(encoding="utf-8")

    outputs = run("sample")
    assert outputs

    required = [
        resolve_path(config, "data.sample_file"),
        resolve_path(config, "data.cleaned_file"),
        resolve_path(config, "data.features_file"),
        resolve_path(config, "data.predictions_file"),
        resolve_path(config, "data.monitoring_predictions_file"),
        resolve_path(config, "data.anomaly_file"),
        resolve_path(config, "data.events_file"),
        resolve_path(config, "models.predictor"),
        resolve_path(config, "models.anomaly_detector"),
        resolve_path(config, "reports.metrics_dir") / "backtest_metrics.json",
        resolve_path(config, "reports.confidence_file"),
        resolve_path(config, "reports.metrics_dir") / "data_health.json",
        resolve_path(config, "reports.monitoring_file")
        if "monitoring_file" in config.get("reports", {})
        else resolve_path(config, "reports.metrics_dir") / "monitoring.json",
        resolve_path(config, "monitoring.history_file"),
        resolve_path(config, "reports.metrics_dir") / "evaluation_summary.json",
        resolve_path(config, "reports.metrics_dir") / "run_manifest.json",
    ]
    assert resolve_path(config, "reports.confidence_file") in outputs
    for path in required:
        assert path.exists()
        assert path.stat().st_size > 0

    manifest_path = resolve_path(config, "reports.metrics_dir") / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["run"]["data_source"] == "Sample Data"
    assert manifest["data_contract"]["target"] == "target_next_hour_aqi"
    assert manifest["metrics"]["monitoring"]["status"] in {
        "stable",
        "warning",
        "critical",
        "insufficient_data",
    }
    assert manifest["metrics"]["monitoring_history"]["entry_count"] >= 1
    monitoring_predictions = resolve_path(config, "data.monitoring_predictions_file")
    monitoring_frame = pd.read_csv(monitoring_predictions)
    assert set(monitoring_frame["prediction_stage"]) == {"rolling_origin_oof", "final_test"}
    assert (
        pd.to_datetime(monitoring_frame["training_cutoff"])
        < pd.to_datetime(monitoring_frame["datetime"])
    ).all()
    assert all(artifact["exists"] for artifact in manifest["artifacts"])
