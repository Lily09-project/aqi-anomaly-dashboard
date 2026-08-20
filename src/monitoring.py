from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd


DEFAULT_THRESHOLDS = {
    "mean_shift_warning": 0.5,
    "mean_shift_critical": 1.0,
    "mae_increase_warning_pct": 25.0,
    "coverage_shortfall_warning": 0.05,
    "coverage_shortfall_critical": 0.10,
}


def _empty_report(reason: str, policy: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "monitoring_version": "1.0",
        "policy": dict(policy or {}),
        "status": "insufficient_data",
        "reason": reason,
        "reference_window": {"start": None, "end": None, "rows": 0},
        "current_window": {"start": None, "end": None, "rows": 0},
        "signals": [],
        "prediction": {"status": "insufficient_data"},
        "coverage": {},
        "retraining": {"recommended": False, "reasons": []},
    }


def _prepare(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "datetime" not in frame:
        return pd.DataFrame()
    prepared = frame.copy()
    prepared["datetime"] = pd.to_datetime(prepared["datetime"], errors="coerce")
    return prepared.dropna(subset=["datetime"]).sort_values("datetime")


def _window_payload(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"start": None, "end": None, "rows": 0}
    return {
        "start": frame["datetime"].min().isoformat(),
        "end": frame["datetime"].max().isoformat(),
        "rows": int(len(frame)),
    }


def _status_rank(status: str) -> int:
    return {"stable": 0, "warning": 1, "critical": 2}.get(status, 0)


def _distribution_signal(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    column: str,
    thresholds: Mapping[str, float],
) -> dict[str, Any] | None:
    if column not in reference or column not in current:
        return None
    reference_values = pd.to_numeric(reference[column], errors="coerce").dropna()
    current_values = pd.to_numeric(current[column], errors="coerce").dropna()
    if reference_values.empty or current_values.empty:
        return None
    reference_mean = float(reference_values.mean())
    current_mean = float(current_values.mean())
    reference_std = float(reference_values.std(ddof=0))
    scale = reference_std if reference_std > 1e-9 else 1.0
    shift = abs(current_mean - reference_mean) / scale
    if shift >= thresholds["mean_shift_critical"]:
        status = "critical"
    elif shift >= thresholds["mean_shift_warning"]:
        status = "warning"
    else:
        status = "stable"
    return {
        "column": column,
        "reference_mean": round(reference_mean, 4),
        "current_mean": round(current_mean, 4),
        "reference_std": round(reference_std, 4),
        "standardized_mean_shift": round(float(shift), 4),
        "status": status,
    }


def _prediction_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    thresholds: Mapping[str, float],
) -> dict[str, Any]:
    required = {"actual_next_hour_aqi", "predicted_next_hour_aqi"}
    if not required.issubset(reference) or not required.issubset(current):
        return {"status": "insufficient_data"}

    def error_values(frame: pd.DataFrame) -> pd.Series:
        actual = pd.to_numeric(frame["actual_next_hour_aqi"], errors="coerce")
        predicted = pd.to_numeric(frame["predicted_next_hour_aqi"], errors="coerce")
        return (actual - predicted).abs().dropna()

    reference_error = error_values(reference)
    current_error = error_values(current)
    if reference_error.empty or current_error.empty:
        return {"status": "insufficient_data"}
    reference_mae = float(reference_error.mean())
    current_mae = float(current_error.mean())
    if reference_mae > 1e-9:
        change_pct = (current_mae - reference_mae) / reference_mae * 100
    else:
        change_pct = 0.0 if current_mae <= 1e-9 else 100.0
    warning = thresholds["mae_increase_warning_pct"]
    status = "critical" if change_pct >= warning * 2 else "warning" if change_pct >= warning else "stable"
    return {
        "reference_rows": int(len(reference_error)),
        "current_rows": int(len(current_error)),
        "reference_mae": round(reference_mae, 4),
        "current_mae": round(current_mae, 4),
        "mae_change_pct": round(float(change_pct), 2),
        "status": status,
    }


def _coverage_drift(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    thresholds: Mapping[str, float],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for level in (80, 95):
        lower = f"lower_{level}_aqi"
        upper = f"upper_{level}_aqi"
        required = {"actual_next_hour_aqi", lower, upper}
        if not required.issubset(reference) or not required.issubset(current):
            continue

        def coverage(frame: pd.DataFrame) -> tuple[float | None, int]:
            values = frame[["actual_next_hour_aqi", lower, upper]].apply(pd.to_numeric, errors="coerce").dropna()
            if values.empty:
                return None, 0
            covered = values["actual_next_hour_aqi"].between(values[lower], values[upper], inclusive="both")
            return float(covered.mean()), int(len(values))

        reference_coverage, reference_rows = coverage(reference)
        current_coverage, current_rows = coverage(current)
        if reference_coverage is None or current_coverage is None:
            continue
        target = level / 100
        shortfall = max(0.0, target - current_coverage)
        if shortfall >= thresholds["coverage_shortfall_critical"]:
            status = "critical"
        elif shortfall >= thresholds["coverage_shortfall_warning"]:
            status = "warning"
        else:
            status = "stable"
        output[str(level)] = {
            "target": target,
            "reference": round(reference_coverage, 4),
            "current": round(current_coverage, 4),
            "reference_rows": reference_rows,
            "current_rows": current_rows,
            "status": status,
        }
    return output


def build_monitoring_report(
    features: pd.DataFrame,
    predictions: pd.DataFrame,
    reference_days: int = 14,
    current_days: int = 7,
    thresholds: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    active_thresholds = {**DEFAULT_THRESHOLDS, **dict(thresholds or {})}
    policy = {
        "reference_days": int(reference_days),
        "current_days": int(current_days),
        "thresholds": {str(key): float(value) for key, value in active_thresholds.items()},
    }
    feature_frame = _prepare(features)
    prediction_frame = _prepare(predictions)
    if feature_frame.empty:
        return _empty_report("features_missing_or_empty", policy)

    latest = feature_frame["datetime"].max()
    current_cutoff = latest - pd.Timedelta(days=current_days)
    reference_cutoff = current_cutoff - pd.Timedelta(days=reference_days)
    current_features = feature_frame[feature_frame["datetime"] > current_cutoff]
    reference_features = feature_frame[
        (feature_frame["datetime"] > reference_cutoff) & (feature_frame["datetime"] <= current_cutoff)
    ]
    if len(current_features) < 24 or len(reference_features) < 24:
        return _empty_report("reference_or_current_window_too_short", policy)

    current_predictions = prediction_frame[prediction_frame["datetime"] > current_cutoff]
    reference_predictions = prediction_frame[
        (prediction_frame["datetime"] > reference_cutoff) & (prediction_frame["datetime"] <= current_cutoff)
    ]
    signals = [
        signal
        for column in ("aqi", "pm25")
        if (signal := _distribution_signal(reference_features, current_features, column, active_thresholds))
    ]
    prediction = _prediction_drift(reference_predictions, current_predictions, active_thresholds)
    coverage = _coverage_drift(reference_predictions, current_predictions, active_thresholds)

    statuses = [signal["status"] for signal in signals]
    statuses.append(str(prediction.get("status", "stable")))
    statuses.extend(str(item.get("status", "stable")) for item in coverage.values())
    status = max(statuses, key=_status_rank, default="stable")
    reasons = [f"{signal['column']} distribution drift" for signal in signals if signal["status"] != "stable"]
    if prediction.get("status") in {"warning", "critical"}:
        reasons.append("prediction MAE increased")
    reasons.extend(f"{level}% interval coverage below target" for level, item in coverage.items() if item["status"] != "stable")
    return {
        "monitoring_version": "1.0",
        "policy": policy,
        "status": status,
        "reason": None,
        "reference_window": _window_payload(reference_features),
        "current_window": _window_payload(current_features),
        "signals": signals,
        "prediction": prediction,
        "coverage": coverage,
        "thresholds": active_thresholds,
        "retraining": {"recommended": bool(reasons), "reasons": reasons},
    }
