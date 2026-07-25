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
from src.train_predictor import _time_split, train_predictor
from src.utils import load_config, load_model, resolve_path


def _prepare_pipeline():
    generate_sample_aqi(days=7)
    preprocess(mode="sample")
    return build_features()


def test_models_train_save_load_and_predict_quickly():
    config = load_config()
    features = _prepare_pipeline()
    start = time.perf_counter()
    train_predictor()
    train_anomaly_model()
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
