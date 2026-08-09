from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluate import evaluate
from src.features import build_features
from src.fetch_aqi_data import fetch_aqi_data
from src.generate_sample_data import generate_sample_aqi
from src.preprocess import preprocess
from src.smoke_test import run_smoke_test
from src.train_anomaly_model import train_anomaly_model
from src.train_predictor import train_predictor
from src.utils import latest_csv, load_config, project_path, resolve_path


def _ensure_dirs() -> None:
    config = load_config()
    dirs = [
        config["data"]["raw_dir"],
        Path(config["data"]["sample_file"]).parent,
        Path(config["data"]["cleaned_file"]).parent,
        Path(config["models"]["predictor"]).parent,
        config["reports"]["metrics_dir"],
        config["reports"]["figures_dir"],
    ]
    for rel in dirs:
        project_path(rel).mkdir(parents=True, exist_ok=True)


def _step(name: str, fn: Callable[[], object]) -> object:
    print(f"[RUN] {name}...")
    try:
        result = fn()
    except Exception as exc:
        print(f"[ERROR] {name} failed: {exc}")
        raise
    print(f"[OK] {name}")
    return result


def _output_summary() -> list[Path]:
    config = load_config()
    outputs = [
        resolve_path(config, "data.sample_file"),
        resolve_path(config, "data.cleaned_file"),
        resolve_path(config, "data.features_file"),
        resolve_path(config, "data.predictions_file"),
        resolve_path(config, "data.anomaly_file"),
        resolve_path(config, "data.events_file"),
        resolve_path(config, "models.predictor"),
        resolve_path(config, "models.anomaly_detector"),
        resolve_path(config, "reports.metrics_dir") / "predictor_metrics.json",
        resolve_path(config, "reports.metrics_dir") / "anomaly_metrics.json",
        resolve_path(config, "reports.metrics_dir") / "backtest_metrics.json",
        resolve_path(config, "reports.confidence_file"),
        resolve_path(config, "reports.metrics_dir") / "data_health.json",
        resolve_path(config, "reports.metrics_dir") / "evaluation_summary.json",
        resolve_path(config, "reports.figures_dir") / "aqi_trend.png",
        resolve_path(config, "reports.figures_dir") / "prediction_vs_actual.png",
        resolve_path(config, "reports.figures_dir") / "anomaly_cases.png",
    ]
    existing = [path for path in outputs if path.exists()]
    print("[SUMMARY] Generated files:")
    for path in existing:
        print(f"  - {path.relative_to(ROOT)}")
    return existing


def run(mode: str = "sample") -> list[Path]:
    _step("Create required folders", _ensure_dirs)
    input_path: Path | None = None
    if mode == "api":
        input_path = _step("Fetch API data", fetch_aqi_data)
        if input_path is None:
            config = load_config()
            input_path = latest_csv(resolve_path(config, "data.raw_dir"))
            if input_path is None:
                print("Falling back to sample mode because API and local raw data are unavailable.")
                mode = "sample"
            else:
                print(f"Using local raw fallback: {input_path}")

    if mode == "sample":
        _step("Generate sample data", generate_sample_aqi)

    _step("Preprocess data", lambda: preprocess(mode=mode, input_path=input_path))
    _step("Build features", build_features)
    _step("Train predictor model", train_predictor)
    _step("Train anomaly model", train_anomaly_model)
    _step("Evaluate outputs", evaluate)
    _step("Run smoke checks", run_smoke_test)
    print("Pipeline finished successfully.")
    return _output_summary()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AQI dashboard pipeline.")
    parser.add_argument("--mode", choices=["sample", "api"], default="sample")
    args = parser.parse_args()
    run(args.mode)


if __name__ == "__main__":
    main()
