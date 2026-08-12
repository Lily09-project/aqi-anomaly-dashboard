from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.model_reliability import build_reliability_report
from src.forecast_confidence import (
    apply_prediction_intervals,
    build_confidence_metrics,
    calibrate_interval_widths,
    classify_threshold_watch,
)
from src.utils import ensure_parent, load_config, resolve_path, save_model, write_json


@dataclass
class NumpyLinearModel:
    columns: list[str]
    coefficients: list[float]

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        matrix = np.c_[np.ones(len(x)), x[self.columns].to_numpy(dtype=float)]
        return matrix @ np.array(self.coefficients)


@dataclass
class MovingAverageModel:
    """Serializable baseline that follows the predictor ``predict`` contract."""

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return x["rolling_3h_aqi"].fillna(x["lag_1_aqi"]).to_numpy(dtype=float)
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


def temporal_train_validation_test_split(
    df: pd.DataFrame,
    validation_ratio: float,
    test_ratio: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create non-overlapping chronological splits using whole timestamps."""
    ordered = df.sort_values("datetime").reset_index(drop=True)
    timestamps = pd.Index(ordered["datetime"].drop_duplicates().sort_values())
    if len(timestamps) < 3:
        raise ValueError("At least three unique timestamps are required for train/validation/test splitting.")

    validation_count = max(1, int(len(timestamps) * validation_ratio))
    test_count = max(1, int(len(timestamps) * test_ratio))
    while validation_count + test_count >= len(timestamps):
        if validation_count >= test_count and validation_count > 1:
            validation_count -= 1
        elif test_count > 1:
            test_count -= 1
        else:
            raise ValueError("Not enough timestamps for a chronological train/validation/test split.")

    validation_start = timestamps[-(validation_count + test_count)]
    test_start = timestamps[-test_count]
    train = ordered[ordered["datetime"] < validation_start].copy()
    validation = ordered[(ordered["datetime"] >= validation_start) & (ordered["datetime"] < test_start)].copy()
    test = ordered[ordered["datetime"] >= test_start].copy()
    if train.empty or validation.empty or test.empty:
        raise ValueError("Chronological train/validation/test split produced an empty partition.")
    return train, validation, test


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


def _predict_candidates(models: dict[str, object], frame: pd.DataFrame, feature_cols: list[str]) -> dict[str, np.ndarray]:
    predictions: dict[str, np.ndarray] = {
        "moving_average": frame["rolling_3h_aqi"].fillna(frame["lag_1_aqi"]).to_numpy(dtype=float)
    }
    for name, model in models.items():
        if model is not None:
            predictions[name] = model.predict(frame[feature_cols])
    return predictions


def _model_metrics(y_true: np.ndarray, predictions: dict[str, np.ndarray]) -> dict[str, dict[str, float]]:
    return {name: _metrics(y_true, predicted) for name, predicted in predictions.items()}


def select_model_from_backtest(backtest: dict[str, object], available_models: list[str]) -> str:
    """Select from pre-test aggregate RMSE, requiring learned models to beat the baseline."""
    aggregate = backtest.get("aggregate", {})
    if not isinstance(aggregate, dict) or "moving_average" not in aggregate:
        raise ValueError("Backtest must include moving_average aggregate metrics.")
    baseline_rmse = float(aggregate["moving_average"]["rmse"])
    learned = [name for name in available_models if name in aggregate]
    if not learned:
        return "moving_average"
    winner = min(learned, key=lambda name: (float(aggregate[name]["rmse"]), name))
    return winner if float(aggregate[winner]["rmse"]) < baseline_rmse else "moving_average"
def rolling_origin_backtest(
    df: pd.DataFrame,
    feature_cols: list[str],
    random_state: int,
    folds: int,
    calibration_model: str | None = None,
    collect_calibration_candidates: bool = False,
) -> dict[str, object]:
    """Evaluate every candidate on successive future windows without look-ahead."""
    ordered = df.sort_values("datetime").reset_index(drop=True)
    timestamps = pd.Index(ordered["datetime"].drop_duplicates().sort_values())
    initial_train_count = max(12, int(len(timestamps) * 0.45))
    available = len(timestamps) - initial_train_count
    fold_count = min(max(1, folds), available)
    if available <= 0:
        return {"fold_count": 0, "folds": [], "aggregate": {}}

    window = max(1, available // fold_count)
    fold_rows: list[dict[str, object]] = []
    aggregate: dict[str, list[dict[str, float]]] = {}
    calibration_residuals: list[float] = []
    candidate_residuals: dict[str, list[float]] = {}
    calibration_starts: list[pd.Timestamp] = []
    calibration_ends: list[pd.Timestamp] = []
    for fold_index in range(fold_count):
        test_start_index = initial_train_count + fold_index * window
        test_end_index = len(timestamps) if fold_index == fold_count - 1 else min(
            len(timestamps), test_start_index + window
        )
        if test_start_index >= test_end_index:
            continue
        train_end = timestamps[test_start_index]
        test_start = timestamps[test_start_index]
        test_end = timestamps[test_end_index - 1]
        train = ordered[ordered["datetime"] < train_end]
        test = ordered[(ordered["datetime"] >= test_start) & (ordered["datetime"] <= test_end)]
        if train.empty or test.empty:
            continue
        models, _ = _fit_model(train, train["target_next_hour_aqi"].to_numpy(dtype=float), feature_cols, random_state)
        candidate_predictions = _predict_candidates(models, test, feature_cols)
        actual = test["target_next_hour_aqi"].to_numpy(dtype=float)
        metrics = _model_metrics(actual, candidate_predictions)
        if collect_calibration_candidates:
            for model_name, predicted in candidate_predictions.items():
                candidate_residuals.setdefault(model_name, []).extend(np.abs(actual - predicted).tolist())
        if collect_calibration_candidates:
            calibration_starts.append(pd.Timestamp(test_start))
            calibration_ends.append(pd.Timestamp(test_end))
        if calibration_model is not None:
            if calibration_model not in candidate_predictions:
                raise ValueError(f"Calibration model is unavailable: {calibration_model}")
            calibration_residuals.extend(np.abs(actual - candidate_predictions[calibration_model]).tolist())
            calibration_starts.append(pd.Timestamp(test_start))
            calibration_ends.append(pd.Timestamp(test_end))
        for model_name, model_values in metrics.items():
            aggregate.setdefault(model_name, []).append(model_values)
        fold_rows.append(
            {
                "fold": fold_index + 1,
                "train_end": str(train["datetime"].max()),
                "test_start": str(test_start),
                "test_end": str(test_end),
                "test_rows": int(len(test)),
                "model_comparison": metrics,
            }
        )

    aggregate_metrics = {
        model_name: {
            metric: round(float(np.mean([fold[metric] for fold in model_folds])), 4)
            for metric in ("mae", "rmse", "r2")
        }
        for model_name, model_folds in aggregate.items()
    }
    result: dict[str, object] = {"fold_count": len(fold_rows), "folds": fold_rows, "aggregate": aggregate_metrics}
    if collect_calibration_candidates:
        period = {
            "start": str(min(calibration_starts)) if calibration_starts else "",
            "end": str(max(calibration_ends)) if calibration_ends else "",
        }
        result["calibration_candidates"] = {
            model_name: {
                "model": model_name,
                "residuals": residuals,
                "rows": len(residuals),
                "period": period,
            }
            for model_name, residuals in candidate_residuals.items()
        }
    if calibration_model is not None:
        result["calibration"] = {
            "model": calibration_model,
            "residuals": calibration_residuals,
            "rows": len(calibration_residuals),
            "period": {
                "start": str(min(calibration_starts)) if calibration_starts else "",
                "end": str(max(calibration_ends)) if calibration_ends else "",
            },
        }
    return result


def train_predictor() -> dict[str, object]:
    config = load_config()
    df = pd.read_csv(resolve_path(config, "data.features_file"), parse_dates=["datetime"])
    feature_cols = config["train"]["feature_columns"]
    target_col = "target_next_hour_aqi"
    train_df, validation_df, test_df = temporal_train_validation_test_split(
        df,
        float(config["train"].get("validation_ratio", 0.15)),
        float(config["train"]["test_ratio"]),
    )
    selection_models, _ = _fit_model(
        train_df,
        train_df[target_col].to_numpy(dtype=float),
        feature_cols,
        int(config["random_state"]),
    )
    validation_predictions = _predict_candidates(selection_models, validation_df, feature_cols)
    validation_metrics = _model_metrics(validation_df[target_col].to_numpy(dtype=float), validation_predictions)

    train_validation_df = pd.concat([train_df, validation_df], ignore_index=True).sort_values("datetime")
    backtest = rolling_origin_backtest(
        train_validation_df,
        feature_cols,
        int(config["random_state"]),
        int(config["train"].get("backtest_folds", 3)),
        collect_calibration_candidates=True,
    )
    calibration_candidates = backtest.pop("calibration_candidates")
    candidate_models = [
        name
        for name in ("linear_regression", "random_forest")
        if name in selection_models and selection_models[name] is not None
    ]
    preferred_model = select_model_from_backtest(backtest, candidate_models)
    calibration = calibration_candidates[preferred_model]

    final_models, _ = _fit_model(
        train_validation_df,
        train_validation_df[target_col].to_numpy(dtype=float),
        feature_cols,
        int(config["random_state"]),
    )
    serializable_models = {**final_models, "moving_average": MovingAverageModel()}
    predictions = _predict_candidates(final_models, test_df, feature_cols)
    model_metrics = _model_metrics(test_df[target_col].to_numpy(dtype=float), predictions)
    output_cols = ["datetime", "site_name", "county", "aqi", "pm25", target_col]
    for display_col in ["county_display", "site_name_display"]:
        if display_col in test_df.columns and display_col not in output_cols:
            output_cols.insert(3, display_col)
    test_out = test_df[output_cols].copy()
    test_out["actual_next_hour_aqi"] = test_df[target_col].to_numpy(dtype=float)
    for name, pred in predictions.items():
        test_out[f"pred_{name}"] = np.round(pred, 3)
    preferred_col = f"pred_{preferred_model}"
    test_out["predicted_next_hour_aqi"] = test_out[preferred_col]
    best_metrics = model_metrics[preferred_model]
    baseline_metrics = model_metrics["moving_average"]

    confidence_config = config.get("forecast_confidence", {})
    confidence_levels = tuple(float(value) for value in confidence_config.get("levels", [0.8, 0.95]))
    confidence_thresholds = [float(value) for value in confidence_config.get("aqi_thresholds", [50, 100, 150, 200, 300])]
    interval_widths = calibrate_interval_widths(calibration["residuals"], confidence_levels)
    test_out = apply_prediction_intervals(test_out, "predicted_next_hour_aqi", interval_widths)
    test_out = classify_threshold_watch(test_out, confidence_thresholds)
    confidence_metrics = build_confidence_metrics(
        test_out,
        widths=interval_widths,
        calibration_rows=int(calibration["rows"]),
        calibration_period=calibration["period"],
        final_test_period={
            "start": str(test_df["datetime"].min()),
            "end": str(test_df["datetime"].max()),
        },
        thresholds=confidence_thresholds,
    )
    reliability = build_reliability_report(test_out)
    metrics: dict[str, object] = {
        "mae": best_metrics["mae"],
        "rmse": best_metrics["rmse"],
        "r2": best_metrics["r2"],
        "baseline_mae": baseline_metrics["mae"],
        "baseline_rmse": baseline_metrics["rmse"],
        "baseline_r2": baseline_metrics["r2"],
        "best_model": preferred_model,
        "model_comparison": model_metrics,
        "validation_model_comparison": validation_metrics,
        "selection_basis": "rolling_origin_rmse",
        "split_rows": {
            "train": int(len(train_df)),
            "validation": int(len(validation_df)),
            "final_test": int(len(test_df)),
        },
        "reliability": reliability,
        "limitation_note": "This is a next-hour AQI nowcasting demo. Models are selected by pre-test rolling-origin RMSE and reported once on a later final test split.",
    }

    ensure_parent(resolve_path(config, "data.predictions_file"))
    test_out.to_csv(resolve_path(config, "data.predictions_file"), index=False, encoding="utf-8")
    save_model(resolve_path(config, "models.predictor"), serializable_models[preferred_model])
    write_json(resolve_path(config, "reports.metrics_dir") / "predictor_metrics.json", metrics)
    write_json(resolve_path(config, "reports.metrics_dir") / "backtest_metrics.json", backtest)
    write_json(resolve_path(config, "reports.confidence_file"), confidence_metrics)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    metrics = train_predictor()
    print(f"Predictor metrics: {metrics}")


if __name__ == "__main__":
    main()
