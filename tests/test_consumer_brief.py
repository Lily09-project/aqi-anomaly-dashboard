from __future__ import annotations

import pandas as pd

from src.consumer_brief import (
    aqi_guidance,
    build_consumer_summary,
    build_export_frame,
    export_csv_bytes,
    format_observation_status,
)


def test_aqi_guidance_uses_official_category_boundaries() -> None:
    expected = {
        50: "良好",
        51: "普通",
        100: "普通",
        101: "對敏感族群不健康",
        150: "對敏感族群不健康",
        151: "對所有族群不健康",
        200: "對所有族群不健康",
        201: "非常不健康",
        300: "非常不健康",
        301: "危害",
    }

    for value, category in expected.items():
        guidance = aqi_guidance(value)
        assert guidance["category"] == category
        assert guidance["general"]
        assert guidance["sensitive"]


def test_observation_status_distinguishes_sample_from_api_data() -> None:
    observed_at = pd.Timestamp("2026-08-09 23:00")

    sample = format_observation_status(observed_at, "Sample Data")
    api = format_observation_status(observed_at, "API Data")

    assert sample["label"] == "模擬資料時點"
    assert sample["value"] == "2026/08/09 23:00"
    assert "不代表即時觀測" in sample["detail"]
    assert api["label"] == "最新觀測時間"


def test_consumer_summary_is_clear_about_source_and_limitations() -> None:
    features = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-09 22:00", "2026-08-09 23:00"]),
            "site_name_display": ["松山測站", "松山測站"],
            "aqi": [72.0, 82.0],
            "pm25": [23.0, 27.0],
        }
    )
    anomalies = pd.DataFrame({"is_anomaly": [False, True]})

    summary = build_consumer_summary(features, anomalies, "Sample Data", "松山測站")

    assert "Sample Data（模擬資料）" in summary
    assert "2026/08/09 23:00" in summary
    assert "AQI：82.0（普通）" in summary
    assert "異常觀測：1 筆" in summary
    assert "不是環境部即時監測資訊" in summary
    assert "松山測站" in summary


def test_export_csv_is_excel_friendly_and_excludes_internal_features() -> None:
    features = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-09 23:00"]),
            "county_display": ["臺北市"],
            "site_name_display": ["松山測站"],
            "aqi": [82.0],
            "pm25": [27.0],
            "rolling_12h_aqi": [75.0],
            "target_aqi": [84.0],
        }
    )

    exported = build_export_frame(features)
    payload = export_csv_bytes(features)

    assert exported.columns.tolist() == ["時間", "縣市", "測站", "AQI", "PM2.5"]
    assert payload.startswith(b"\xef\xbb\xbf")
    decoded = payload.decode("utf-8-sig")
    assert "松山測站" in decoded
    assert "rolling_12h_aqi" not in decoded
    assert "target_aqi" not in decoded


def test_consumer_helpers_handle_empty_data() -> None:
    empty = pd.DataFrame()

    assert build_export_frame(empty).empty
    assert "尚無可用資料" in build_consumer_summary(empty, empty, "Sample Data", "全部測站")
    assert format_observation_status(None, "Sample Data")["value"] == "尚無資料"

def test_consumer_summary_tolerates_optional_measurements() -> None:
    features = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-09 23:00"]),
            "aqi": [42.0],
        }
    )

    summary = build_consumer_summary(features, pd.DataFrame(), "API Data", "全部測站")

    assert "AQI：42.0（良好）" in summary
    assert "PM2.5：N/A" in summary
