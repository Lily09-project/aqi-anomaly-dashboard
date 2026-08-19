from __future__ import annotations

import json
import math
from typing import Any

import pandas as pd

from src.app_helpers import data_quality_summary

AQI_GUIDANCE = (
    {
        "max_aqi": 50,
        "category": "良好",
        "general": "適合正常戶外活動。",
        "sensitive": "可正常進行戶外活動。",
    },
    {
        "max_aqi": 100,
        "category": "普通",
        "general": "可正常進行戶外活動。",
        "sensitive": "對空氣污染特別敏感者，若出現不適請留意身體反應。",
    },
    {
        "max_aqi": 150,
        "category": "對敏感族群不健康",
        "general": "一般民眾若感到不適，可減少長時間或劇烈的戶外活動。",
        "sensitive": "兒童、長者及心肺疾病者宜減少戶外活動與體力消耗。",
    },
    {
        "max_aqi": 200,
        "category": "對所有族群不健康",
        "general": "建議減少長時間或劇烈的戶外活動，出現不適時應休息。",
        "sensitive": "兒童、長者及心肺疾病者宜留在室內並減少體力消耗。",
    },
    {
        "max_aqi": 300,
        "category": "非常不健康",
        "general": "建議減少戶外活動；學童宜停止戶外活動。",
        "sensitive": "應留在室內並避免體力消耗，必要時採取個人防護。",
    },
    {
        "max_aqi": float("inf"),
        "category": "危害",
        "general": "應避免戶外活動、關閉門窗，必要時採取個人防護。",
        "sensitive": "應留在室內並避免體力消耗，持續不適時尋求專業協助。",
    },
)


PUBLIC_EXPORT_COLUMNS = {
    "datetime": "時間",
    "county_display": "縣市",
    "site_name_display": "測站",
    "aqi": "AQI",
    "pm25": "PM2.5",
    "pm10": "PM10",
    "o3": "臭氧 O3",
    "co": "一氧化碳 CO",
    "wind_speed": "風速",
    "wind_directions": "風向",
    "data_source": "資料來源",
}


def aqi_guidance(value: Any) -> dict[str, Any]:
    """Return the official AQI category and concise activity guidance."""
    try:
        numeric_value = max(0.0, float(value))
    except (TypeError, ValueError):
        return {
            "category": "無資料",
            "general": "目前沒有足夠資料可提供活動建議。",
            "sensitive": "請改以環境部官方即時資訊作為判斷依據。",
            "max_aqi": None,
        }
    for item in AQI_GUIDANCE:
        if numeric_value <= item["max_aqi"]:
            return dict(item)
    return dict(AQI_GUIDANCE[-1])


def format_observation_status(observed_at: Any, data_source: str) -> dict[str, str]:
    timestamp = pd.to_datetime(observed_at, errors="coerce")
    is_sample = data_source != "API Data"
    if pd.isna(timestamp):
        value = "尚無資料"
    else:
        value = timestamp.strftime("%Y/%m/%d %H:%M")
    return {
        "label": "模擬資料時點" if is_sample else "最新觀測時間",
        "value": value,
        "detail": (
            "此時間來自本地模擬資料，不代表即時觀測。"
            if is_sample
            else "資料時效取決於上游 API 更新頻率。"
        ),
    }


def _latest_values(features: pd.DataFrame) -> tuple[pd.Timestamp | None, float | None, float | None]:
    if features.empty or "datetime" not in features:
        return None, None, None
    datetimes = pd.to_datetime(features["datetime"], errors="coerce")
    if not datetimes.notna().any():
        return None, None, None
    latest_time = datetimes.max()
    latest_rows = features.loc[datetimes == latest_time]
    latest_aqi = pd.to_numeric(latest_rows.get("aqi"), errors="coerce").mean()
    latest_pm25 = pd.to_numeric(latest_rows.get("pm25"), errors="coerce").mean()
    return (
        latest_time,
        None if pd.isna(latest_aqi) else float(latest_aqi),
        None if pd.isna(latest_pm25) else float(latest_pm25),
    )


def build_consumer_summary(
    features: pd.DataFrame,
    anomalies: pd.DataFrame,
    data_source: str,
    selection_label: str,
) -> str:
    """Build a plain-text summary suitable for user download and sharing."""
    latest_time, latest_aqi, latest_pm25 = _latest_values(features)
    source_label = "API Data" if data_source == "API Data" else "Sample Data（模擬資料）"
    status = format_observation_status(latest_time, data_source)
    if latest_aqi is None:
        return (
            "台灣 AQI 監測摘要\n"
            f"篩選範圍：{selection_label}\n"
            f"資料來源：{source_label}\n"
            "狀態：尚無可用資料\n"
            "請以環境部官方即時資訊作為健康與行程決策依據。\n"
        )

    guidance = aqi_guidance(latest_aqi)
    anomaly_count = 0
    if not anomalies.empty and "is_anomaly" in anomalies:
        anomaly_count = int(anomalies["is_anomaly"].fillna(False).astype(bool).sum())
    pm25_text = "N/A" if latest_pm25 is None else f"{latest_pm25:.1f} μg/m³"
    disclaimer = (
        "此內容不是環境部即時監測資訊，僅供本地展示與測試。"
        if data_source != "API Data"
        else "資料時效取決於上游 API；健康與行程決策請以環境部官方資訊為準。"
    )
    return (
        "台灣 AQI 監測摘要\n"
        f"篩選範圍：{selection_label}\n"
        f"資料來源：{source_label}\n"
        f"{status['label']}：{status['value']}\n"
        f"AQI：{latest_aqi:.1f}（{guidance['category']}）\n"
        f"PM2.5：{pm25_text}\n"
        f"異常觀測：{anomaly_count} 筆\n"
        f"一般活動建議：{guidance['general']}\n"
        f"敏感族群建議：{guidance['sensitive']}\n"
        f"注意：{disclaimer}\n"
    )


def build_export_frame(features: pd.DataFrame) -> pd.DataFrame:
    """Keep user-facing observations and exclude internal model features/targets."""
    available = [column for column in PUBLIC_EXPORT_COLUMNS if column in features.columns]
    exported = features.loc[:, available].copy()
    if "datetime" in exported:
        datetimes = pd.to_datetime(exported["datetime"], errors="coerce")
        exported["datetime"] = datetimes.dt.strftime("%Y/%m/%d %H:%M")
    return exported.rename(columns=PUBLIC_EXPORT_COLUMNS)


def export_csv_bytes(features: pd.DataFrame) -> bytes:
    csv_text = build_export_frame(features).to_csv(index=False, lineterminator="\n")
    return csv_text.encode("utf-8-sig")
def _json_safe(value: Any) -> Any:
    """Convert pandas and NumPy scalar values into JSON-safe primitives."""
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return _json_safe(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _report_number(value: Any, digits: int = 4) -> int | float | None:
    safe_value = _json_safe(value)
    if safe_value is None or isinstance(safe_value, bool):
        return None
    try:
        numeric = float(safe_value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    rounded = round(numeric, digits)
    return int(rounded) if rounded.is_integer() else rounded


def _report_timestamp(value: Any) -> str | None:
    timestamp = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(timestamp) else timestamp.strftime("%Y-%m-%dT%H:%M:%S")


def _report_model_comparison(metrics: dict[str, Any] | None) -> dict[str, dict[str, int | float | None]]:
    comparison = metrics.get("model_comparison", {}) if isinstance(metrics, dict) else {}
    if not isinstance(comparison, dict):
        return {}
    output: dict[str, dict[str, int | float | None]] = {}
    for model_name, values in comparison.items():
        if not isinstance(values, dict):
            continue
        output[str(model_name)] = {
            metric: _report_number(values.get(metric))
            for metric in ("mae", "rmse", "r2")
        }
    return output


def _report_station_priority(risk_brief: pd.DataFrame | None, limit: int = 10) -> list[dict[str, Any]]:
    if not isinstance(risk_brief, pd.DataFrame) or risk_brief.empty:
        return []
    rows: list[dict[str, Any]] = []
    for rank, (_, row) in enumerate(risk_brief.head(limit).iterrows(), start=1):
        rows.append(
            {
                "rank": rank,
                "station": str(row.get("site_name_display") or row.get("site_name") or "未知測站"),
                "county": str(row.get("county_display") or "未知地區"),
                "as_of": _report_timestamp(row.get("as_of")),
                "latest_aqi": _report_number(row.get("latest_aqi"), 1),
                "latest_pm25": _report_number(row.get("latest_pm25"), 1),
                "predicted_next_hour_aqi": _report_number(row.get("predicted_next_hour_aqi"), 1),
                "priority_score": _report_number(row.get("priority_score"), 0),
                "attention_level": str(row.get("attention_level") or "一般監測"),
                "evidence": str(row.get("evidence_summary") or "無額外判讀依據"),
            }
        )
    return rows


def _report_confidence(metrics: dict[str, Any] | None) -> dict[str, Any]:
    source = metrics if isinstance(metrics, dict) else {}
    intervals = source.get("intervals", {})
    output_intervals: dict[str, dict[str, int | float | None]] = {}
    if isinstance(intervals, dict):
        for level in ("80", "95"):
            values = intervals.get(level, {})
            if isinstance(values, dict):
                output_intervals[f"{level}%"] = {
                    "calibration_residual_quantile": _report_number(values.get("residual_quantile")),
                    "empirical_coverage": _report_number(values.get("empirical_coverage")),
                    "mean_width": _report_number(values.get("mean_width"), 2),
                }
    return {
        "method": source.get("method", "未提供"),
        "calibration_rows": _report_number(source.get("calibration_rows"), 0),
        "intervals": output_intervals,
        "limitation": source.get(
            "limitation_note",
            "預測區間是歷史殘差校準的決策支援範圍，不是官方警報或保證機率。",
        ),
    }


def build_reliability_report(
    *,
    features: pd.DataFrame,
    predictions: pd.DataFrame | None,
    anomalies: pd.DataFrame | None,
    risk_brief: pd.DataFrame | None,
    predictor_metrics: dict[str, Any] | None,
    anomaly_metrics: dict[str, Any] | None,
    confidence_metrics: dict[str, Any] | None,
    data_health: dict[str, Any] | None,
    data_source: str,
    selection_label: str,
    filter_metadata: dict[str, Any] | None = None,
    generated_at: Any | None = None,
) -> dict[str, Any]:
    """Build a shareable, public-facing reliability report for the current scope."""
    quality = data_quality_summary(features)
    predictor = predictor_metrics if isinstance(predictor_metrics, dict) else {}
    anomaly = anomaly_metrics if isinstance(anomaly_metrics, dict) else {}
    health = data_health if isinstance(data_health, dict) else {}
    reliability = predictor.get("reliability", {})
    if not isinstance(reliability, dict):
        reliability = {}
    baseline_improvement = reliability.get("baseline_improvement", {})
    if not isinstance(baseline_improvement, dict):
        baseline_improvement = {}

    selected_model = predictor.get("best_model") or predictor.get("selected_model") or "未提供"
    model_reliability = {
        "selected_model": selected_model,
        "metric_scope": "pipeline_final_test",
        "selection_basis": predictor.get("selection_basis", "未提供"),
        "final_test": {
            "mae": _report_number(predictor.get("mae")),
            "rmse": _report_number(predictor.get("rmse")),
            "r2": _report_number(predictor.get("r2")),
        },
        "model_comparison": _report_model_comparison(predictor),
        "split_rows": _json_safe(predictor.get("split_rows", {})),
        "baseline_improvement": {
            "mae_reduction_pct": _report_number(baseline_improvement.get("mae_reduction_pct"), 2),
            "rmse_reduction_pct": _report_number(baseline_improvement.get("rmse_reduction_pct"), 2),
        },
        "limitation": predictor.get(
            "limitation_note",
            "這是下一小時 AQI nowcasting，模型表現不能直接視為正式預警能力。",
        ),
    }
    anomaly_detection = {
        "metric_scope": "pipeline_evaluation",
        "precision": _report_number(anomaly.get("precision")),
        "recall": _report_number(anomaly.get("recall")),
        "f1": _report_number(anomaly.get("f1")),
        "anomaly_rate": _report_number(anomaly.get("anomaly_rate")),
        "anomaly_count": _report_number(anomaly.get("anomaly_count"), 0),
        "model_comparison": _json_safe(anomaly.get("model_comparison", {})),
        "limitation": anomaly.get(
            "limitation_note",
            "異常偵測 metrics 使用 pseudo-label，不等同於人工驗證的污染事件標註。",
        ),
    }
    safe_filter_metadata = {str(key): _json_safe(value) for key, value in (filter_metadata or {}).items()}
    safe_generated_at = _report_timestamp(generated_at) or pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    prediction_rows = int(len(predictions)) if isinstance(predictions, pd.DataFrame) else 0
    anomaly_rows = int(len(anomalies)) if isinstance(anomalies, pd.DataFrame) else 0
    anomaly_flagged_rows = (
        int(anomalies["is_anomaly"].fillna(False).astype(bool).sum())
        if isinstance(anomalies, pd.DataFrame) and "is_anomaly" in anomalies
        else 0
    )
    return {
        "report_version": "1.0",
        "report_type": "taiwan_aqi_reliability_summary",
        "generated_at_utc": safe_generated_at,
        "selection": {
            "label": selection_label,
            "data_source": data_source,
            **safe_filter_metadata,
        },
        "data_quality": {
            "rows": int(quality.get("rows", 0)),
            "missing_cells": int(quality.get("missing_cells", 0)),
            "station_count": int(quality.get("site_count", 0)),
            "date_range": quality.get("date_range", "無資料"),
            "status": health.get("status", "尚未評估"),
            "duplicate_station_timestamps": _report_number(health.get("duplicate_station_timestamps"), 0),
            "stale_station_count": _report_number(health.get("stale_station_count"), 0),
            "largest_gap_hours": _report_number(health.get("largest_gap_hours"), 2),
            "prediction_rows": prediction_rows,
            "anomaly_rows": anomaly_rows,
            "anomaly_flagged_rows": anomaly_flagged_rows,
        },
        "station_priority": _report_station_priority(risk_brief),
        "model_reliability": model_reliability,
        "forecast_confidence": _report_confidence(confidence_metrics),
        "anomaly_detection": anomaly_detection,
        "limitations": [
            "資料來源若標示為 Sample Data，代表本地模擬資料，不代表即時監測。",
            "預測目標是同一測站下一小時 AQI，屬於 nowcasting / next-hour forecasting。",
            "模型與異常偵測結果是決策支援資訊，不是官方健康、行程或污染警報。",
            "異常偵測目前以 pseudo-label 評估，正式應用前需要真實事件標註與外部驗證。",
        ],
    }


def export_reliability_report_bytes(report: dict[str, Any]) -> bytes:
    """Serialize the reliability report as UTF-8 JSON without internal debug fields."""
    return (json.dumps(_json_safe(report), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
