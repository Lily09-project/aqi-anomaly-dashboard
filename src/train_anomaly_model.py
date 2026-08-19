from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.anomaly_events import build_anomaly_events
from src.utils import load_config, resolve_path, save_model, write_csv, write_json


@dataclass
class ZScoreAnomalyModel:
    columns: list[str]
    means: list[float]
    stds: list[float]
    threshold: float

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        values = x[self.columns].to_numpy(dtype=float)
        z = np.abs((values - np.array(self.means)) / np.array(self.stds))
        return np.where(np.nanmax(z, axis=1) > self.threshold, -1, 1)


def _classification_metrics(labels: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    tp = float(((labels == 1) & (predicted == 1)).sum())
    fp = float(((labels == 0) & (predicted == 1)).sum())
    fn = float(((labels == 1) & (predicted == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}


def train_anomaly_model() -> dict[str, object]:
    config = load_config()
    df = pd.read_csv(resolve_path(config, "data.features_file"), parse_dates=["datetime"])
    feature_cols = ["aqi", "pm25", "pm10", "o3", "co", "wind_speed", "aqi_diff", "pm25_diff"]
    threshold = float(config["anomaly"]["zscore_threshold"])
    pseudo_aqi_threshold = float(config["anomaly"].get("pseudo_aqi_threshold", 100))
    pseudo_pm25_threshold = float(config["anomaly"].get("pseudo_pm25_threshold", 35))

    rolling_mean = df.groupby("site_name")["aqi"].transform(lambda s: s.shift(1).rolling(12, min_periods=4).mean())
    rolling_std = df.groupby("site_name")["aqi"].transform(lambda s: s.shift(1).rolling(12, min_periods=4).std())
    pseudo_label = (
        (df["aqi"] > pseudo_aqi_threshold)
        | (df["pm25"] > pseudo_pm25_threshold)
        | (df["aqi"] > rolling_mean + threshold * rolling_std)
    ).fillna(False)
    df["pseudo_anomaly"] = pseudo_label.astype(int)

    timestamps = pd.Index(df["datetime"].drop_duplicates().sort_values())
    split_idx = min(len(timestamps) - 1, max(1, int(len(timestamps) * (1 - float(config["train"]["test_ratio"])))) )
    cutoff = timestamps[split_idx]
    train_mask = df["datetime"] < cutoff
    eval_mask = ~train_mask
    means = df.loc[train_mask, feature_cols].mean()
    stds = df.loc[train_mask, feature_cols].std().replace(0, 1)
    zscore_any = ((df[feature_cols] - means).abs() / stds).max(axis=1) > threshold
    df["zscore_anomaly"] = zscore_any.astype(int)

    try:
        from sklearn.ensemble import IsolationForest  # type: ignore

        model = IsolationForest(
            contamination=float(config["anomaly"]["contamination"]),
            random_state=int(config["random_state"]),
        )
        model.fit(df.loc[train_mask, feature_cols])
        pred_raw = model.predict(df[feature_cols])
    except ImportError:
        model = ZScoreAnomalyModel(
            columns=feature_cols,
            means=means.astype(float).tolist(),
            stds=stds.astype(float).tolist(),
            threshold=threshold,
        )
        pred_raw = model.predict(df[feature_cols])

    df["isolation_forest_anomaly"] = (pred_raw == -1).astype(int)
    df["anomaly_score"] = df[["pseudo_anomaly", "zscore_anomaly", "isolation_forest_anomaly"]].mean(axis=1)
    df["is_anomaly"] = (df["anomaly_score"] >= 0.34).astype(int)

    isolation_metrics = _classification_metrics(
        df.loc[eval_mask, "pseudo_anomaly"].to_numpy(), df.loc[eval_mask, "isolation_forest_anomaly"].to_numpy()
    )
    zscore_metrics = _classification_metrics(
        df.loc[eval_mask, "pseudo_anomaly"].to_numpy(), df.loc[eval_mask, "zscore_anomaly"].to_numpy()
    )
    events = build_anomaly_events(df, max_gap_hours=int(config["anomaly"].get("event_gap_hours", 1)))
    metrics = {
        "precision": isolation_metrics["precision"],
        "recall": isolation_metrics["recall"],
        "f1": isolation_metrics["f1"],
        "anomaly_rate": round(float(df["is_anomaly"].mean()), 4),
        "pseudo_label_positive_rate": round(float(df["pseudo_anomaly"].mean()), 4),
        "zscore": zscore_metrics,
        "isolation_forest": isolation_metrics,
        "anomaly_count": int(df["is_anomaly"].sum()),
        "event_count": int(len(events)),
        "model_comparison": {"zscore": zscore_metrics, "isolation_forest": isolation_metrics},
        "limitation_note": "Metrics are evaluated against pseudo-labels, not verified ground-truth pollution incident labels.",
    }

    cols = ["datetime", "site_name", "county"]
    for display_col in ["county_display", "site_name_display"]:
        if display_col in df.columns:
            cols.append(display_col)
    cols += [
        "aqi",
        "pm25",
        "pseudo_anomaly",
        "zscore_anomaly",
        "isolation_forest_anomaly",
        "anomaly_score",
        "is_anomaly",
    ]

    write_csv(df[cols], resolve_path(config, "data.anomaly_file"), index=False, encoding="utf-8")

    write_csv(events, resolve_path(config, "data.events_file"), index=False, encoding="utf-8")
    save_model(resolve_path(config, "models.anomaly_detector"), model)
    write_json(resolve_path(config, "reports.metrics_dir") / "anomaly_metrics.json", metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    metrics = train_anomaly_model()
    print(f"Anomaly metrics: {metrics}")


if __name__ == "__main__":
    main()
