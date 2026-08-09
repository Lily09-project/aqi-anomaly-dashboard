from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluate import evaluate
from src.features import build_features
from src.generate_sample_data import generate_sample_aqi
from src.preprocess import preprocess
from src.train_anomaly_model import train_anomaly_model
from src.train_predictor import train_predictor
from src.utils import load_config, resolve_path


def test_evaluation_writes_metrics_and_figures():
    config = load_config()
    generate_sample_aqi(days=7)
    preprocess(mode="sample")
    build_features()
    train_predictor()
    train_anomaly_model()
    summary = evaluate()

    metrics_dir = resolve_path(config, "reports.metrics_dir")
    predictor_metrics = json.loads((metrics_dir / "predictor_metrics.json").read_text(encoding="utf-8"))
    anomaly_metrics = json.loads((metrics_dir / "anomaly_metrics.json").read_text(encoding="utf-8"))
    confidence_metrics = json.loads((metrics_dir / "forecast_confidence.json").read_text(encoding="utf-8"))

    assert summary["rows"]["features"] > 0
    assert {
        "mae",
        "rmse",
        "r2",
        "baseline_mae",
        "baseline_rmse",
        "baseline_r2",
        "selection_basis",
        "split_rows",
        "limitation_note",
    }.issubset(
        predictor_metrics
    )
    assert {"precision", "recall", "f1", "anomaly_rate", "pseudo_label_positive_rate", "event_count", "limitation_note"}.issubset(
        anomaly_metrics
    )
    assert (metrics_dir / "evaluation_summary.json").exists()
    assert (metrics_dir / "backtest_metrics.json").exists()
    assert (metrics_dir / "data_health.json").exists()
    assert resolve_path(config, "data.events_file").exists()
    assert summary["rows"]["anomaly_events"] >= 0
    assert summary["forecast_confidence"]["method"] == "rolling_origin_conformal"
    assert confidence_metrics["intervals"]["95"]["empirical_coverage"] >= 0
    assert "status" in summary["data_health"]
    for figure in ["aqi_trend.png", "prediction_vs_actual.png", "anomaly_cases.png"]:
        assert (resolve_path(config, "reports.figures_dir") / figure).exists()
