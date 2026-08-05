from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features import build_features
from src.generate_sample_data import generate_sample_aqi
from src.preprocess import preprocess
from src.train_anomaly_model import train_anomaly_model
from src.train_predictor import _time_split, rolling_origin_backtest, temporal_train_validation_test_split, train_predictor
from src.utils import load_config, load_model, resolve_path


def _prepare_pipeline():
    generate_sample_aqi(days=7)
    preprocess(mode="sample")
    return build_features()


def test_models_train_save_load_and_predict_quickly():
    config = load_config()
    features = _prepare_pipeline()
    start = time.perf_counter()
    predictor_metrics = train_predictor()
    anomaly_metrics = train_anomaly_model()
    elapsed = time.perf_counter() - start

    assert elapsed < 30
    predictor_path = resolve_path(config, "models.predictor")
    anomaly_path = resolve_path(config, "models.anomaly_detector")
    assert predictor_path.exists()
    assert anomaly_path.exists()
    predictions = pd.read_csv(resolve_path(config, "data.predictions_file"))
    anomaly_results = pd.read_csv(resolve_path(config, "data.anomaly_file"))
    assert {"county_display", "site_name_display"}.issubset(predictions.columns)
    assert {"county_display", "site_name_display"}.issubset(anomaly_results.columns)
    assert predictor_metrics["selection_basis"] == "validation_rmse"
    assert set(predictor_metrics["split_rows"]) == {"train", "validation", "final_test"}
    assert anomaly_metrics["event_count"] >= 0
    assert resolve_path(config, "data.events_file").exists()
    assert (resolve_path(config, "reports.metrics_dir") / "backtest_metrics.json").exists()

    predictor = load_model(predictor_path)
    anomaly = load_model(anomaly_path)
    batch = features.head(8)
    pred = predictor.predict(batch[config["train"]["feature_columns"]])
    assert len(pred) == len(batch)

    anomaly_features = ["aqi", "pm25", "pm10", "o3", "co", "wind_speed", "aqi_diff", "pm25_diff"]
    anomaly_pred = anomaly.predict(batch[anomaly_features])
    assert len(anomaly_pred) == len(batch)

    if importlib.util.find_spec("joblib"):
        import joblib  # type: ignore

        assert joblib.load(predictor_path) is not None


def test_time_split_keeps_each_timestamp_on_one_side():
    timestamps = pd.date_range("2026-06-01", periods=5, freq="h")
    frame = pd.DataFrame(
        {
            "datetime": [timestamp for timestamp in timestamps for _ in range(2)],
            "site_name": ["A", "B"] * len(timestamps),
        }
    )
    train, test = _time_split(frame, test_ratio=0.25)

    assert not set(train["datetime"]).intersection(set(test["datetime"]))
    assert train["datetime"].max() < test["datetime"].min()


def test_temporal_split_and_backtest_keep_future_rows_out_of_training():
    features = _prepare_pipeline()
    train, validation, test = temporal_train_validation_test_split(features, validation_ratio=0.15, test_ratio=0.2)

    assert train["datetime"].max() < validation["datetime"].min() < test["datetime"].min()
    assert not set(train["datetime"]).intersection(validation["datetime"])
    assert not set(validation["datetime"]).intersection(test["datetime"])

    config = load_config()
    backtest = rolling_origin_backtest(
        features,
        config["train"]["feature_columns"],
        int(config["random_state"]),
        folds=3,
    )
    assert backtest["fold_count"] == 3
    assert {"moving_average", "linear_regression"}.issubset(backtest["aggregate"])
    for fold in backtest["folds"]:
        assert pd.Timestamp(fold["train_end"]) < pd.Timestamp(fold["test_start"])
