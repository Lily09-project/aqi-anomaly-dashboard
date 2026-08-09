from __future__ import annotations

from typing import Any

import pandas as pd


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
