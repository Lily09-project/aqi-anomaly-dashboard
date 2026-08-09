from __future__ import annotations

from collections.abc import Iterable
from math import ceil
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_LEVELS = (0.8, 0.95)
DEFAULT_THRESHOLDS = (50.0, 100.0, 150.0, 200.0, 300.0)


def _level_key(level: float) -> str:
    return str(int(round(level * 100)))


def calibrate_interval_widths(
    residuals: Iterable[float],
    levels: Iterable[float] = DEFAULT_LEVELS,
) -> dict[str, float]:
    """Return finite-sample conformal widths from absolute calibration residuals."""
    values = np.asarray(list(residuals), dtype=float)
    values = np.abs(values[np.isfinite(values)])
    if len(values) < 2:
        raise ValueError("Prediction interval calibration requires at least two finite residuals.")
    values.sort()

    widths: dict[str, float] = {}
    for level in sorted(set(float(item) for item in levels)):
        if not 0 < level < 1:
            raise ValueError("Prediction interval levels must be between zero and one.")
        rank = min(len(values), max(1, ceil((len(values) + 1) * level)))
        widths[_level_key(level)] = float(values[rank - 1])
    return widths


def apply_prediction_intervals(
    frame: pd.DataFrame,
    prediction_col: str,
    widths: dict[str, float],
) -> pd.DataFrame:
    """Append symmetric AQI intervals while preventing physically invalid negatives."""
    if prediction_col not in frame:
        raise ValueError(f"Missing prediction column: {prediction_col}")
    result = frame.copy()
    prediction = pd.to_numeric(result[prediction_col], errors="coerce")
    for key, width in widths.items():
        finite_width = float(width)
        if not np.isfinite(finite_width) or finite_width < 0:
            raise ValueError("Prediction interval widths must be finite and non-negative.")
        result[f"lower_{key}_aqi"] = (prediction - finite_width).clip(lower=0).round(3)
        result[f"upper_{key}_aqi"] = (prediction + finite_width).round(3)
    return result


def _next_threshold(prediction: float, thresholds: list[float]) -> float | None:
    return next((threshold for threshold in thresholds if threshold > prediction), None)


def classify_threshold_watch(
    frame: pd.DataFrame,
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
) -> pd.DataFrame:
    """Classify whether empirical intervals cross the next AQI breakpoint."""
    required = {"predicted_next_hour_aqi", "upper_80_aqi", "upper_95_aqi"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing threshold-watch columns: {sorted(missing)}")

    resolved_thresholds = sorted({float(value) for value in thresholds if np.isfinite(float(value))})
    if not resolved_thresholds:
        raise ValueError("At least one finite AQI threshold is required.")

    result = frame.copy()
    levels: list[str] = []
    reasons: list[str] = []
    next_thresholds: list[float | None] = []
    for _, row in result.iterrows():
        prediction = float(row["predicted_next_hour_aqi"])
        threshold = _next_threshold(prediction, resolved_thresholds)
        next_thresholds.append(threshold)
        if threshold is None:
            levels.append("區間穩定")
            reasons.append("點預測已高於最高設定門檻，請直接檢視 AQI 數值")
        elif float(row["upper_80_aqi"]) >= threshold:
            levels.append("跨級關注")
            reasons.append(f"80% 預測區間上界跨過 AQI {threshold:g}")
        elif float(row["upper_95_aqi"]) >= threshold:
            levels.append("不確定性關注")
            reasons.append(f"95% 預測區間上界跨過 AQI {threshold:g}")
        else:
            levels.append("區間穩定")
            reasons.append(f"95% 預測區間未跨過下一門檻 AQI {threshold:g}")

    result["next_aqi_threshold"] = next_thresholds
    result["threshold_watch_level"] = levels
    result["threshold_watch_reason"] = reasons
    return result


def build_confidence_metrics(
    frame: pd.DataFrame,
    widths: dict[str, float],
    calibration_rows: int,
    calibration_period: dict[str, str],
    final_test_period: dict[str, str],
    thresholds: Iterable[float] = DEFAULT_THRESHOLDS,
) -> dict[str, Any]:
    """Report final-test coverage without changing calibration widths."""
    actual = pd.to_numeric(frame["actual_next_hour_aqi"], errors="coerce")
    intervals: dict[str, dict[str, float]] = {}
    for key, width in widths.items():
        lower = pd.to_numeric(frame[f"lower_{key}_aqi"], errors="coerce")
        upper = pd.to_numeric(frame[f"upper_{key}_aqi"], errors="coerce")
        valid = actual.notna() & lower.notna() & upper.notna()
        coverage = ((actual[valid] >= lower[valid]) & (actual[valid] <= upper[valid])).mean()
        intervals[key] = {
            "residual_quantile": round(float(width), 4),
            "empirical_coverage": round(float(coverage), 4),
            "mean_width": round(float((upper[valid] - lower[valid]).mean()), 4),
        }

    return {
        "method": "rolling_origin_conformal",
        "calibration_rows": int(calibration_rows),
        "calibration_period": calibration_period,
        "final_test_period": final_test_period,
        "intervals": intervals,
        "aqi_thresholds": [float(value) for value in thresholds],
        "limitation_note": (
            "Intervals use historical rolling-origin residuals and report empirical final-test coverage. "
            "They are decision-support ranges, not official alerts or guaranteed probabilities."
        ),
    }
