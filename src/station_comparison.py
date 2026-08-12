from __future__ import annotations

from typing import Any

import pandas as pd

from src.consumer_brief import aqi_guidance
from src.risk_brief import build_station_risk_brief, describe_anomaly_evidence


COMPARISON_COLUMNS = [
    "site_name",
    "site_name_display",
    "county_display",
    "observed_at",
    "data_lag_hours",
    "freshness_state",
    "current_aqi",
    "aqi_category",
    "pm25",
    "predicted_next_hour_aqi",
    "lower_80_aqi",
    "upper_80_aqi",
    "forecast_change",
    "baseline_aqi",
    "aqi_vs_baseline",
    "recent_6h_change",
    "attention_level",
    "context_evidence",
    "is_anomaly",
    "anomaly_evidence",
    "comparison_value",
    "comparison_basis",
]

EXPORT_COLUMNS = {
    "site_name_display": "測站",
    "county_display": "縣市",
    "observed_at": "觀測時間",
    "freshness_state": "資料狀態",
    "current_aqi": "目前 AQI",
    "aqi_category": "AQI 等級",
    "pm25": "PM2.5",
    "predicted_next_hour_aqi": "下一小時預測 AQI",
    "lower_80_aqi": "80% 區間下界",
    "upper_80_aqi": "80% 區間上界",
    "forecast_change": "預測變化",
    "baseline_aqi": "本站同時段基準",
    "aqi_vs_baseline": "相對本站基準",
    "recent_6h_change": "近 6 小時變化",
    "attention_level": "關注程度",
    "context_evidence": "脈絡證據",
    "is_anomaly": "異常觀測",
    "anomaly_evidence": "異常證據",
}


def _empty_comparison() -> pd.DataFrame:
    return pd.DataFrame(columns=COMPARISON_COLUMNS)


def _prepare_frame(data: pd.DataFrame | None) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame) or data.empty:
        return pd.DataFrame()
    frame = data.copy()
    if "datetime" in frame:
        frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    return frame


def _numeric(value: Any) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(numeric) else float(numeric)


def _display_text(value: Any, fallback: str) -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _matching_row(frame: pd.DataFrame, site_name: str, observed_at: pd.Timestamp) -> pd.Series | None:
    if frame.empty or not {"site_name", "datetime"}.issubset(frame.columns):
        return None
    matches = frame[
        (frame["site_name"].astype(str) == site_name)
        & (frame["datetime"] == observed_at)
    ]
    return matches.iloc[-1] if not matches.empty else None


def build_station_comparison(
    features: pd.DataFrame,
    predictions: pd.DataFrame | None = None,
    anomalies: pd.DataFrame | None = None,
    selected_sites: list[str] | tuple[str, ...] | None = None,
    stale_after_hours: float = 2,
    reference_features: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build a latest-observation comparison without mixing station timelines."""
    if stale_after_hours < 0:
        raise ValueError("stale_after_hours must be non-negative")
    feature_frame = _prepare_frame(features)
    required = {"site_name", "datetime", "aqi"}
    if feature_frame.empty or not required.issubset(feature_frame.columns):
        return _empty_comparison()
    feature_frame = feature_frame.dropna(subset=["site_name", "datetime", "aqi"])
    if feature_frame.empty:
        return _empty_comparison()

    if selected_sites:
        selected = {str(site) for site in selected_sites}
        display_values = feature_frame.get("site_name_display", pd.Series(index=feature_frame.index, dtype="object"))
        feature_frame = feature_frame[
            feature_frame["site_name"].astype(str).isin(selected)
            | display_values.astype(str).isin(selected)
        ]
    if feature_frame.empty:
        return _empty_comparison()

    latest_rows = (
        feature_frame.sort_values(["site_name", "datetime"])
        .groupby("site_name", sort=False, as_index=False)
        .tail(1)
        .copy()
    )
    newest_observation = pd.Timestamp(latest_rows["datetime"].max())
    prediction_frame = _prepare_frame(predictions)
    anomaly_frame = _prepare_frame(anomalies)
    context = build_station_risk_brief(
        latest_rows,
        reference_features=reference_features if reference_features is not None else feature_frame,
        predictions=prediction_frame,
        anomalies=anomaly_frame,
    )
    context_by_site = context.set_index("site_name") if not context.empty else pd.DataFrame()

    records: list[dict[str, Any]] = []
    for _, latest in latest_rows.iterrows():
        site_name = str(latest["site_name"])
        observed_at = pd.Timestamp(latest["datetime"])
        current_aqi = _numeric(latest.get("aqi"))
        if current_aqi is None:
            continue
        prediction_row = _matching_row(prediction_frame, site_name, observed_at)
        anomaly_row = _matching_row(anomaly_frame, site_name, observed_at)
        prediction = _numeric(prediction_row.get("predicted_next_hour_aqi")) if prediction_row is not None else None
        lower_80 = _numeric(prediction_row.get("lower_80_aqi")) if prediction_row is not None else None
        upper_80 = _numeric(prediction_row.get("upper_80_aqi")) if prediction_row is not None else None
        data_lag_hours = max(0.0, (newest_observation - observed_at).total_seconds() / 3600)
        is_anomaly = bool(_numeric(anomaly_row.get("is_anomaly")) == 1) if anomaly_row is not None else False
        evidence = describe_anomaly_evidence(anomaly_row) if anomaly_row is not None else "未提供異常結果"
        comparison_value = prediction if prediction is not None else current_aqi
        context_row = context_by_site.loc[site_name] if site_name in context_by_site.index else None
        records.append(
            {
                "site_name": site_name,
                "site_name_display": _display_text(latest.get("site_name_display"), site_name),
                "county_display": _display_text(latest.get("county_display"), "未知地區"),
                "observed_at": observed_at,
                "data_lag_hours": round(data_lag_hours, 1),
                "freshness_state": "資料較舊" if data_lag_hours > stale_after_hours else "可比較",
                "current_aqi": round(current_aqi, 1),
                "aqi_category": aqi_guidance(current_aqi)["category"],
                "pm25": _numeric(latest.get("pm25")),
                "predicted_next_hour_aqi": prediction,
                "lower_80_aqi": lower_80,
                "upper_80_aqi": upper_80,
                "forecast_change": None if prediction is None else round(prediction - current_aqi, 1),
                "baseline_aqi": _numeric(context_row.get("baseline_aqi")) if context_row is not None else None,
                "aqi_vs_baseline": _numeric(context_row.get("aqi_vs_baseline")) if context_row is not None else None,
                "recent_6h_change": _numeric(context_row.get("recent_6h_change")) if context_row is not None else None,
                "attention_level": str(context_row.get("attention_level")) if context_row is not None else "資料不足",
                "context_evidence": str(context_row.get("evidence_summary")) if context_row is not None else "脈絡資料不足",
                "is_anomaly": is_anomaly,
                "anomaly_evidence": evidence,
                "comparison_value": comparison_value,
                "comparison_basis": "下一小時預測 AQI" if prediction is not None else "目前 AQI",
            }
        )
    if not records:
        return _empty_comparison()
    return (
        pd.DataFrame(records, columns=COMPARISON_COLUMNS)
        .sort_values(["freshness_state", "comparison_value", "site_name_display"])
        .reset_index(drop=True)
    )


def choose_recommended_station(comparison: pd.DataFrame) -> dict[str, object]:
    """Choose the lowest comparable forecast/current AQI and explain the basis."""
    empty_result: dict[str, object] = {
        "site_name": None,
        "site_name_display": None,
        "basis": None,
        "value": None,
    }
    if comparison.empty or not {"freshness_state", "comparison_value"}.issubset(comparison.columns):
        return empty_result
    candidates = comparison[comparison["freshness_state"] == "可比較"].copy()
    candidates["comparison_value"] = pd.to_numeric(candidates["comparison_value"], errors="coerce")
    candidates = candidates.dropna(subset=["comparison_value"])
    if candidates.empty:
        return empty_result
    selected = candidates.sort_values(["comparison_value", "site_name_display"]).iloc[0]
    return {
        "site_name": selected["site_name"],
        "site_name_display": selected["site_name_display"],
        "basis": selected["comparison_basis"],
        "value": float(selected["comparison_value"]),
    }


def export_comparison_csv(comparison: pd.DataFrame) -> bytes:
    available = [column for column in EXPORT_COLUMNS if column in comparison.columns]
    exported = comparison.loc[:, available].copy()
    if "observed_at" in exported:
        timestamps = pd.to_datetime(exported["observed_at"], errors="coerce")
        exported["observed_at"] = timestamps.dt.strftime("%Y/%m/%d %H:%M")
    if "is_anomaly" in exported:
        exported["is_anomaly"] = exported["is_anomaly"].map({True: "是", False: "否"}).fillna("否")
    exported = exported.rename(columns=EXPORT_COLUMNS)
    return exported.to_csv(index=False, lineterminator="\n").encode("utf-8-sig")
