from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


ACTUAL_COLUMN = "actual_next_hour_aqi"
AQI_BINS = [-np.inf, 50, 100, 150, 200, 300, np.inf]
AQI_LABELS = ["0-50", "51-100", "101-150", "151-200", "201-300", "301+"]


def _metrics(frame: pd.DataFrame, prediction_col: str) -> dict[str, float | int]:
    actual = frame[ACTUAL_COLUMN].to_numpy(dtype=float)
    predicted = frame[prediction_col].to_numpy(dtype=float)
    error = actual - predicted
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))
    denominator = float(np.sum((actual - actual.mean()) ** 2))
    r2 = float(1 - np.sum(error**2) / denominator) if len(actual) > 1 and denominator else 0.0
    return {
        "rows": int(len(frame)),
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
    }


def build_reliability_report(
    predictions: pd.DataFrame,
    baseline_col: str = "pred_moving_average",
    prediction_col: str = "predicted_next_hour_aqi",
) -> dict[str, Any]:
    """Summarize finite final-test errors by station and observed AQI band."""
    required = {ACTUAL_COLUMN, baseline_col, prediction_col}
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError("Missing reliability columns: " + ", ".join(missing))

    station_col = "site_name_display" if "site_name_display" in predictions else "site_name"
    working = predictions.copy()
    if station_col not in working:
        station_col = "_station"
        working[station_col] = "All stations"
    for column in required:
        working[column] = pd.to_numeric(working[column], errors="coerce")
    finite = np.isfinite(working[[ACTUAL_COLUMN, baseline_col, prediction_col]].to_numpy(dtype=float)).all(axis=1)
    working = working.loc[finite].copy()
    if working.empty:
        return {
            "overall": {"rows": 0, "mae": 0.0, "rmse": 0.0, "r2": 0.0},
            "by_station": [],
            "by_aqi_band": [],
            "baseline_improvement": {"rows": 0},
            "worst_station": {},
        }

    station_rows: list[dict[str, Any]] = []
    for station, group in working.groupby(station_col, sort=True):
        station_rows.append({"station": str(station), **_metrics(group, prediction_col)})

    working["_aqi_band"] = pd.cut(
        working[ACTUAL_COLUMN], bins=AQI_BINS, labels=AQI_LABELS, include_lowest=True
    )
    band_rows: list[dict[str, Any]] = []
    for band, group in working.groupby("_aqi_band", observed=True, sort=False):
        band_rows.append({"aqi_band": str(band), **_metrics(group, prediction_col)})

    model_metrics = _metrics(working, prediction_col)
    baseline_metrics = _metrics(working, baseline_col)
    mae_reduction = float(baseline_metrics["mae"]) - float(model_metrics["mae"])
    rmse_reduction = float(baseline_metrics["rmse"]) - float(model_metrics["rmse"])
    baseline_mae = float(baseline_metrics["mae"])
    baseline_rmse = float(baseline_metrics["rmse"])
    improvement = {
        "rows": int(len(working)),
        "model_mae": model_metrics["mae"],
        "baseline_mae": baseline_metrics["mae"],
        "mae_reduction": round(mae_reduction, 4),
        "mae_reduction_pct": round(mae_reduction / baseline_mae * 100, 2) if baseline_mae else 0.0,
        "model_rmse": model_metrics["rmse"],
        "baseline_rmse": baseline_metrics["rmse"],
        "rmse_reduction": round(rmse_reduction, 4),
        "rmse_reduction_pct": round(rmse_reduction / baseline_rmse * 100, 2) if baseline_rmse else 0.0,
    }
    worst_station = sorted(station_rows, key=lambda row: (-float(row["rmse"]), row["station"]))[0]
    return {
        "overall": model_metrics,
        "by_station": station_rows,
        "by_aqi_band": band_rows,
        "baseline_improvement": improvement,
        "worst_station": worst_station,
    }