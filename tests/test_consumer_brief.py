from __future__ import annotations

import json

import pandas as pd

from src.consumer_brief import (
    aqi_guidance,
    build_consumer_summary,
    build_export_frame,
    build_reliability_report,
    export_reliability_report_bytes,
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
def test_reliability_report_contains_public_quality_and_model_sections() -> None:
    features = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-09 22:00", "2026-08-09 23:00"]),
            "site_name": ["Taipei", "Taipei"],
            "county_display": ["臺北市", "臺北市"],
            "site_name_display": ["松山測站", "松山測站"],
            "aqi": [72.0, 82.0],
            "pm25": [23.0, 27.0],
            "rolling_12h_aqi": [70.0, 75.0],
            "target_aqi": [82.0, None],
        }
    )
    risk_brief = pd.DataFrame(
        {
            "site_name_display": ["松山測站"],
            "county_display": ["臺北市"],
            "as_of": [pd.Timestamp("2026-08-09 23:00")],
            "latest_aqi": [82.0],
            "latest_pm25": [27.0],
            "predicted_next_hour_aqi": [79.0],
            "priority_score": [3],
            "attention_level": ["持續觀察"],
            "evidence_summary": ["下一小時預測 79.0"],
        }
    )
    report = build_reliability_report(
        features=features,
        predictions=pd.DataFrame({"target_aqi": [82.0]}),
        anomalies=pd.DataFrame({"is_anomaly": [False, True]}),
        risk_brief=risk_brief,
        predictor_metrics={
            "best_model": "random_forest",
            "mae": 4.9,
            "rmse": 7.1,
            "r2": 0.82,
            "model_comparison": {"random_forest": {"mae": 4.9, "rmse": 7.1, "r2": 0.82}},
            "split_rows": {"train": 10, "final_test": 2},
            "reliability": {"baseline_improvement": {"mae_reduction_pct": 23.4}},
        },
        anomaly_metrics={"precision": 0.38, "recall": 0.04, "f1": 0.06},
        confidence_metrics={
            "method": "rolling_origin_conformal",
            "calibration_rows": 10,
            "intervals": {"80": {"empirical_coverage": 0.8, "mean_width": 16.0}},
        },
        data_health={"status": "可分析", "largest_gap_hours": 1.0},
        data_source="Sample Data",
        selection_label="松山測站",
        filter_metadata={"county": "臺北市", "start_date": "2026-08-09"},
        generated_at="2026-08-09 23:00",
    )

    payload = export_reliability_report_bytes(report)
    decoded = payload.decode("utf-8")
    parsed = json.loads(decoded)

    assert parsed["report_type"] == "taiwan_aqi_reliability_summary"
    assert parsed["selection"]["data_source"] == "Sample Data"
    assert parsed["data_quality"]["rows"] == 2
    assert parsed["station_priority"][0]["station"] == "松山測站"
    assert parsed["model_reliability"]["final_test"]["mae"] == 4.9
    assert parsed["forecast_confidence"]["intervals"]["80%"]["empirical_coverage"] == 0.8
    assert parsed["anomaly_detection"]["f1"] == 0.06
    assert "target_aqi" not in decoded
    assert "rolling_12h_aqi" not in decoded


def test_reliability_report_handles_empty_optional_inputs() -> None:
    report = build_reliability_report(
        features=pd.DataFrame(),
        predictions=None,
        anomalies=None,
        risk_brief=None,
        predictor_metrics=None,
        anomaly_metrics=None,
        confidence_metrics=None,
        data_health=None,
        data_source="Sample Data",
        selection_label="全部測站",
        generated_at="2026-08-09 23:00",
    )

    assert report["data_quality"]["rows"] == 0
    assert report["station_priority"] == []
    assert json.loads(export_reliability_report_bytes(report).decode("utf-8"))["report_version"] == "1.0"
def test_reliability_report_tolerates_malformed_metrics_and_counts_scope_rows() -> None:
    features = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-09 23:00"]),
            "site_name": ["Taipei"],
            "site_name_display": ["松山測站"],
            "aqi": [82.0],
            "pm25": [27.0],
        }
    )
    predictions = pd.DataFrame({"predicted_next_hour_aqi": [79.0, 80.0]})
    anomalies = pd.DataFrame({"is_anomaly": [True, False, True]})

    report = build_reliability_report(
        features=features,
        predictions=predictions,
        anomalies=anomalies,
        risk_brief=None,
        predictor_metrics={"reliability": None},
        anomaly_metrics=None,
        confidence_metrics=None,
        data_health=None,
        data_source="Sample Data",
        selection_label="松山測站",
        generated_at="2026-08-09 23:00",
    )

    assert report["data_quality"]["prediction_rows"] == 2
    assert report["data_quality"]["anomaly_rows"] == 3
    assert report["data_quality"]["anomaly_flagged_rows"] == 2
    assert report["model_reliability"]["metric_scope"] == "pipeline_final_test"
    assert report["anomaly_detection"]["metric_scope"] == "pipeline_evaluation"
    json.loads(export_reliability_report_bytes(report).decode("utf-8"))
