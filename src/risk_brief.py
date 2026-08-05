from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd


DEFAULT_RISK_POLICY: dict[str, Any] = {
    "lookback_days": 14,
    "recent_window_hours": 6,
    "min_baseline_observations": 3,
    "aqi_attention_threshold": 50,
    "aqi_high_threshold": 100,
    "pm25_threshold": 35,
    "baseline_zscore_watch": 1.0,
    "baseline_zscore_high": 2.0,
    "prediction_rise_threshold": 10,
    "weights": {
        "aqi_attention": 1,
        "aqi_high": 2,
        "pm25_high": 1,
        "baseline_watch": 1,
        "baseline_high": 2,
        "prediction_high": 1,
        "prediction_rise": 1,
        "anomaly_flag": 3,
        "anomaly_consensus": 1,
    },
}

RISK_BRIEF_COLUMNS = [
    "site_name",
    "site_name_display",
    "county_display",
    "as_of",
    "latest_aqi",
    "latest_pm25",
    "baseline_aqi",
    "baseline_samples",
    "aqi_vs_baseline",
    "baseline_zscore",
    "recent_6h_change",
    "trend_label",
    "predicted_next_hour_aqi",
    "prediction_change",
    "anomaly_flag",
    "anomaly_score",
    "priority_score",
    "attention_level",
    "evidence_summary",
]


def _empty_risk_brief() -> pd.DataFrame:
    return pd.DataFrame(columns=RISK_BRIEF_COLUMNS)


def resolve_risk_policy(policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge project policy overrides with explicit, documented defaults."""
    resolved = {**DEFAULT_RISK_POLICY, "weights": dict(DEFAULT_RISK_POLICY["weights"])}
    if not policy:
        return resolved
    for key, value in policy.items():
        if key == "weights" and isinstance(value, dict):
            resolved["weights"].update(value)
        elif key in resolved:
            resolved[key] = value
    return resolved


def _as_frame(data: pd.DataFrame | None) -> pd.DataFrame:
    return data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame()


def _numeric(value: Any) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else float(numeric)


def _describe_trend(change: float | None) -> str:
    if change is None:
        return "資料不足"
    if change >= 8:
        return "上升"
    if change <= -8:
        return "下降"
    return "持平"


def _attention_level(priority_score: int) -> str:
    if priority_score >= 6:
        return "優先檢視"
    if priority_score >= 3:
        return "持續觀察"
    return "一般監測"


def _anomaly_evidence(row: pd.Series) -> list[str]:
    evidence: list[str] = []
    if _numeric(row.get("pseudo_anomaly")) == 1:
        evidence.append("達到規則門檻")
    if _numeric(row.get("zscore_anomaly")) == 1:
        evidence.append("偏離近期分布")
    if _numeric(row.get("isolation_forest_anomaly")) == 1:
        evidence.append("多變量型態偏離")
    if _numeric(row.get("is_anomaly")) == 1 and not evidence:
        evidence.append("異常模型標記")
    return evidence


def describe_anomaly_evidence(row: pd.Series) -> str:
    """Return a concise, non-causal explanation of anomaly model signals."""
    evidence = _anomaly_evidence(row)
    return "、".join(evidence) if evidence else "未達異常旗標"


def _prepare_observations(data: pd.DataFrame | None) -> pd.DataFrame:
    frame = _as_frame(data)
    required = {"site_name", "datetime", "aqi"}
    if frame.empty or not required.issubset(frame.columns):
        return pd.DataFrame(columns=list(required))

    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    frame["aqi"] = pd.to_numeric(frame["aqi"], errors="coerce")
    if "pm25" in frame.columns:
        frame["pm25"] = pd.to_numeric(frame["pm25"], errors="coerce")
    else:
        frame["pm25"] = pd.NA
    return frame.dropna(subset=["site_name", "datetime", "aqi"]).sort_values(["site_name", "datetime"])


def _matching_row(data: pd.DataFrame, site_name: str, as_of: pd.Timestamp) -> pd.Series | None:
    if data.empty or "site_name" not in data or "datetime" not in data:
        return None
    candidates = data[(data["site_name"].astype(str) == str(site_name)) & (data["datetime"] == as_of)]
    return candidates.iloc[-1] if not candidates.empty else None


def _same_hour_baseline(
    history: pd.DataFrame,
    as_of: pd.Timestamp,
    policy: dict[str, Any],
) -> tuple[float | None, int, float | None]:
    start = as_of - pd.Timedelta(days=int(policy["lookback_days"]))
    prior = history[(history["datetime"] < as_of) & (history["datetime"] >= start)].copy()
    same_hour = prior[prior["datetime"].dt.hour == as_of.hour]
    values = same_hour["aqi"].dropna()
    if len(values) < int(policy["min_baseline_observations"]):
        return None, int(len(values)), None
    baseline = float(values.median())
    std = float(values.std(ddof=0))
    return baseline, int(len(values)), std if std > 0 else None


def _recent_change(
    history: pd.DataFrame,
    as_of: pd.Timestamp,
    latest_aqi: float,
    policy: dict[str, Any],
) -> float | None:
    start = as_of - pd.Timedelta(hours=int(policy["recent_window_hours"]))
    recent = history[(history["datetime"] < as_of) & (history["datetime"] >= start)]["aqi"].dropna()
    if recent.empty:
        return None
    return latest_aqi - float(recent.mean())


def _prediction_value(predictions: pd.DataFrame, site_name: str, as_of: pd.Timestamp) -> float | None:
    row = _matching_row(predictions, site_name, as_of)
    if row is None:
        return None
    return _numeric(row.get("predicted_next_hour_aqi"))


def _priority_score(
    latest_aqi: float,
    latest_pm25: float | None,
    baseline_zscore: float | None,
    prediction_change: float | None,
    predicted_aqi: float | None,
    anomaly_row: pd.Series | None,
    policy: dict[str, Any],
) -> int:
    score = 0
    weights = policy["weights"]
    if latest_aqi > float(policy["aqi_high_threshold"]):
        score += int(weights["aqi_high"])
    elif latest_aqi > float(policy["aqi_attention_threshold"]):
        score += int(weights["aqi_attention"])
    if latest_pm25 is not None and latest_pm25 > float(policy["pm25_threshold"]):
        score += int(weights["pm25_high"])
    if baseline_zscore is not None and baseline_zscore >= float(policy["baseline_zscore_high"]):
        score += int(weights["baseline_high"])
    elif baseline_zscore is not None and baseline_zscore >= float(policy["baseline_zscore_watch"]):
        score += int(weights["baseline_watch"])
    if predicted_aqi is not None and predicted_aqi > float(policy["aqi_high_threshold"]):
        score += int(weights["prediction_high"])
    if prediction_change is not None and prediction_change >= float(policy["prediction_rise_threshold"]):
        score += int(weights["prediction_rise"])
    if anomaly_row is not None:
        if _numeric(anomaly_row.get("is_anomaly")) == 1:
            score += int(weights["anomaly_flag"])
        anomaly_score = _numeric(anomaly_row.get("anomaly_score"))
        if anomaly_score is not None and anomaly_score >= 2 / 3:
            score += int(weights["anomaly_consensus"])
    return score


def _evidence_summary(
    latest_aqi: float,
    latest_pm25: float | None,
    baseline: float | None,
    baseline_delta: float | None,
    prediction: float | None,
    anomaly_row: pd.Series | None,
    policy: dict[str, Any],
) -> str:
    evidence: list[str] = []
    if baseline is not None and baseline_delta is not None:
        direction = "高於" if baseline_delta >= 0 else "低於"
        evidence.append(f"AQI {direction}該站同時段基準 {abs(baseline_delta):.1f}")
    else:
        evidence.append("同時段歷史基準資料不足")
    if latest_pm25 is not None and latest_pm25 > float(policy["pm25_threshold"]):
        evidence.append(f"PM2.5 {latest_pm25:.1f} 高於 {float(policy['pm25_threshold']):.0f}")
    if prediction is not None:
        evidence.append(f"下一小時預測 {prediction:.1f}")
    if anomaly_row is not None:
        evidence.extend(_anomaly_evidence(anomaly_row))
    return "；".join(evidence[:4])


def build_station_risk_brief(
    scoped_features: pd.DataFrame,
    reference_features: pd.DataFrame | None = None,
    predictions: pd.DataFrame | None = None,
    anomalies: pd.DataFrame | None = None,
    policy: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Rank stations using only observations before each station's latest timestamp.

    The score is an explainable review priority, not an official AQI alert or a
    causal health-risk estimate. Historical baselines are station-specific and
    exclude the current observation and every future observation.
    """
    resolved_policy = resolve_risk_policy(policy)
    current = _prepare_observations(scoped_features)
    history = _prepare_observations(reference_features if reference_features is not None else scoped_features)
    if current.empty or history.empty:
        return _empty_risk_brief()

    prediction_frame = _as_frame(predictions)
    anomaly_frame = _as_frame(anomalies)
    for frame in (prediction_frame, anomaly_frame):
        if "datetime" in frame:
            frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")

    records: list[dict[str, Any]] = []
    for site_name, station_rows in current.groupby("site_name", sort=False):
        latest = station_rows.sort_values("datetime").iloc[-1]
        as_of = pd.Timestamp(latest["datetime"])
        latest_aqi = float(latest["aqi"])
        latest_pm25 = _numeric(latest.get("pm25"))
        station_history = history[history["site_name"].astype(str) == str(site_name)]
        baseline, baseline_samples, baseline_std = _same_hour_baseline(station_history, as_of, resolved_policy)
        baseline_delta = None if baseline is None else latest_aqi - baseline
        baseline_zscore = None
        if baseline_delta is not None and baseline_std is not None:
            baseline_zscore = baseline_delta / baseline_std
        recent_change = _recent_change(station_history, as_of, latest_aqi, resolved_policy)
        predicted_aqi = _prediction_value(prediction_frame, str(site_name), as_of)
        prediction_change = None if predicted_aqi is None else predicted_aqi - latest_aqi
        anomaly_row = _matching_row(anomaly_frame, str(site_name), as_of)
        priority_score = _priority_score(
            latest_aqi,
            latest_pm25,
            baseline_zscore,
            prediction_change,
            predicted_aqi,
            anomaly_row,
            resolved_policy,
        )
        records.append(
            {
                "site_name": str(site_name),
                "site_name_display": str(latest.get("site_name_display", site_name)),
                "county_display": str(latest.get("county_display", "未知地區")),
                "as_of": as_of,
                "latest_aqi": round(latest_aqi, 1),
                "latest_pm25": None if latest_pm25 is None else round(latest_pm25, 1),
                "baseline_aqi": None if baseline is None else round(baseline, 1),
                "baseline_samples": baseline_samples,
                "aqi_vs_baseline": None if baseline_delta is None else round(baseline_delta, 1),
                "baseline_zscore": None if baseline_zscore is None else round(baseline_zscore, 2),
                "recent_6h_change": None if recent_change is None else round(recent_change, 1),
                "trend_label": _describe_trend(recent_change),
                "predicted_next_hour_aqi": None if predicted_aqi is None else round(predicted_aqi, 1),
                "prediction_change": None if prediction_change is None else round(prediction_change, 1),
                "anomaly_flag": int(_numeric(anomaly_row.get("is_anomaly")) == 1) if anomaly_row is not None else 0,
                "anomaly_score": _numeric(anomaly_row.get("anomaly_score")) if anomaly_row is not None else None,
                "priority_score": priority_score,
                "attention_level": _attention_level(priority_score),
                "evidence_summary": _evidence_summary(
                    latest_aqi,
                    latest_pm25,
                    baseline,
                    baseline_delta,
                    predicted_aqi,
                    anomaly_row,
                    resolved_policy,
                ),
            }
        )

    brief = pd.DataFrame.from_records(records, columns=RISK_BRIEF_COLUMNS)
    return brief.sort_values(
        ["priority_score", "aqi_vs_baseline", "latest_aqi"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)


def select_risk_brief_columns(brief: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    """Return present risk-brief columns without exposing empty placeholder data."""
    existing = [column for column in columns if column in brief.columns]
    return brief[existing].copy() if existing else pd.DataFrame()
