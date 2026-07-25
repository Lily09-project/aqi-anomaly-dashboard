from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.utils import ensure_parent, load_config, resolve_path, save_model, write_json


@dataclass
class NumpyLinearModel:
    columns: list[str]
    coefficients: list[float]

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        matrix = np.c_[np.ones(len(x)), x[self.columns].to_numpy(dtype=float)]
        return matrix @ np.array(self.coefficients)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    err = y_true - y_pred
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err**2)))
    denom = float(np.sum((y_true - y_true.mean()) ** 2))
    r2 = float(1 - np.sum(err**2) / denom) if denom else 0.0
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "r2": round(r2, 4)}


def _time_split(df: pd.DataFrame, test_ratio: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values("datetime").reset_index(drop=True)
    timestamps = pd.Index(df["datetime"].drop_duplicates().sort_values())
    if len(timestamps) < 2:
        raise ValueError("At least two unique timestamps are required for a chronological split.")
    split_idx = min(len(timestamps) - 1, max(1, int(len(timestamps) * (1 - test_ratio))))
    cutoff = timestamps[split_idx]
    return df[df["datetime"] < cutoff].copy(), df[df["datetime"] >= cutoff].copy()


def _fit_model(train_x: pd.DataFrame, train_y: np.ndarray, columns: list[str], random_state: int):
    try:
        from sklearn.ensemble import RandomForestRegressor  # type: ignore
        from sklearn.linear_model import LinearRegression  # type: ignore

        linear = LinearRegression()
        linear.fit(train_x[columns], train_y)
        forest = RandomForestRegressor(n_estimators=120, random_state=random_state, min_samples_leaf=3, n_jobs=-1)
        forest.fit(train_x[columns], train_y)
        return {"linear_regression": linear, "random_forest": forest}, forest
    except ImportError:
        x = np.c_[np.ones(len(train_x)), train_x[columns].to_numpy(dtype=float)]
        coeffs = np.linalg.pinv(x) @ train_y
        model = NumpyLinearModel(columns=columns, coefficients=coeffs.tolist())
        return {"linear_regression": model, "random_forest": None}, model


def train_predictor() -> dict[str, object]:
    config = load_config()
    df = pd.read_csv(resolve_path(config, "data.features_file"), parse_dates=["datetime"])
    feature_cols = config["train"]["feature_columns"]
    target_col = "target_next_hour_aqi"
    train_df, test_df = _time_split(df, float(config["train"]["test_ratio"]))
    train_y = train_df[target_col].to_numpy(dtype=float)
    test_y = test_df[target_col].to_numpy(dtype=float)

    baseline_pred = test_df["rolling_3h_aqi"].fillna(test_df["lag_1_aqi"]).to_numpy(dtype=float)
    models, best_model = _fit_model(train_df, train_y, feature_cols, int(config["random_state"]))
    predictions: dict[str, np.ndarray] = {"moving_average": baseline_pred}
    predictions["linear_regression"] = models["linear_regression"].predict(test_df[feature_cols])
    if models.get("random_forest") is not None:
        predictions["random_forest"] = models["random_forest"].predict(test_df[feature_cols])

    model_metrics = {name: _metrics(test_y, pred) for name, pred in predictions.items()}
    output_cols = ["datetime", "site_name", "county", "aqi", "pm25", target_col]
    for display_col in ["county_display", "site_name_display"]:
        if display_col in test_df.columns and display_col not in output_cols:
            output_cols.insert(3, display_col)
    test_out = test_df[output_cols].copy()
    test_out["actual_next_hour_aqi"] = test_y
    for name, pred in predictions.items():
        test_out[f"pred_{name}"] = np.round(pred, 3)
    candidate_models = [name for name in ("linear_regression", "random_forest") if name in models and models[name] is not None]
    preferred_model = min(candidate_models, key=lambda name: model_metrics[name]["rmse"])
    preferred_col = f"pred_{preferred_model}"
    test_out["predicted_next_hour_aqi"] = test_out[preferred_col]
    best_metrics = model_metrics[preferred_model]
    baseline_metrics = model_metrics["moving_average"]
    metrics: dict[str, object] = {
        "mae": best_metrics["mae"],
        "rmse": best_metrics["rmse"],
        "r2": best_metrics["r2"],
        "baseline_mae": baseline_metrics["mae"],
        "baseline_rmse": baseline_metrics["rmse"],
        "baseline_r2": baseline_metrics["r2"],
        "best_model": preferred_model,
        "model_comparison": model_metrics,
        "limitation_note": "This is a next-hour AQI nowcasting demo. Results are based on sample/API data quality and chronological split.",
    }

    ensure_parent(resolve_path(config, "data.predictions_file"))
    test_out.to_csv(resolve_path(config, "data.predictions_file"), index=False, encoding="utf-8")
    save_model(resolve_path(config, "models.predictor"), models[preferred_model])
    write_json(resolve_path(config, "reports.metrics_dir") / "predictor_metrics.json", metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    metrics = train_predictor()
    print(f"Predictor metrics: {metrics}")


if __name__ == "__main__":
    main()
