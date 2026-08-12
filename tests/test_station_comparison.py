from __future__ import annotations

import pandas as pd

from src.station_comparison import (
    build_station_comparison,
    choose_recommended_station,
    export_comparison_csv,
)


def _comparison_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    features = pd.DataFrame(
        {
            "datetime": pd.to_datetime(
                [
                    "2026-08-12 09:00",
                    "2026-08-12 10:00",
                    "2026-08-12 08:00",
                    "2026-08-12 09:00",
                    "2026-08-12 06:00",
                ]
            ),
            "site_name": ["A", "A", "B", "B", "C"],
            "site_name_display": ["松山測站", "松山測站", "板橋測站", "板橋測站", "西屯測站"],
            "county_display": ["臺北市", "臺北市", "新北市", "新北市", "臺中市"],
            "aqi": [70.0, 65.0, 80.0, 75.0, 40.0],
            "pm25": [25.0, 22.0, 30.0, 28.0, 12.0],
        }
    )
    predictions = pd.DataFrame(
        {
            "datetime": pd.to_datetime(
                ["2026-08-12 09:00", "2026-08-12 10:00", "2026-08-12 09:00", "2026-08-12 06:00"]
            ),
            "site_name": ["A", "A", "B", "C"],
            "predicted_next_hour_aqi": [99.0, 62.0, 68.0, 20.0],
            "lower_80_aqi": [90.0, 56.0, 61.0, 15.0],
            "upper_80_aqi": [108.0, 68.0, 75.0, 25.0],
        }
    )
    anomalies = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-12 10:00", "2026-08-12 09:00"]),
            "site_name": ["A", "B"],
            "is_anomaly": [0, 1],
            "pseudo_anomaly": [0, 1],
            "zscore_anomaly": [0, 1],
            "isolation_forest_anomaly": [0, 0],
        }
    )
    return features, predictions, anomalies


def test_comparison_uses_each_stations_latest_row_and_exact_matching_outputs() -> None:
    features, predictions, anomalies = _comparison_inputs()

    comparison = build_station_comparison(features, predictions, anomalies, ["A", "B"])
    by_site = comparison.set_index("site_name")

    assert by_site.loc["A", "observed_at"] == pd.Timestamp("2026-08-12 10:00")
    assert by_site.loc["A", "current_aqi"] == 65.0
    assert by_site.loc["A", "predicted_next_hour_aqi"] == 62.0
    assert by_site.loc["A", "lower_80_aqi"] == 56.0
    assert by_site.loc["B", "predicted_next_hour_aqi"] == 68.0
    assert bool(by_site.loc["B", "is_anomaly"])
    assert "達到規則門檻" in by_site.loc["B", "anomaly_evidence"]


def test_recommendation_excludes_stale_station_even_when_its_aqi_is_lower() -> None:
    features, predictions, anomalies = _comparison_inputs()
    comparison = build_station_comparison(features, predictions, anomalies, ["A", "B", "C"])

    recommendation = choose_recommended_station(comparison)
    by_site = comparison.set_index("site_name")

    assert by_site.loc["C", "freshness_state"] == "資料較舊"
    assert by_site.loc["C", "data_lag_hours"] == 4.0
    assert recommendation["site_name"] == "A"
    assert recommendation["basis"] == "下一小時預測 AQI"
    assert recommendation["value"] == 62.0


def test_recommendation_falls_back_to_current_aqi_without_predictions() -> None:
    features, _, _ = _comparison_inputs()
    comparison = build_station_comparison(features, selected_sites=["A", "B"])

    recommendation = choose_recommended_station(comparison)

    assert recommendation["site_name"] == "A"
    assert recommendation["basis"] == "目前 AQI"
    assert recommendation["value"] == 65.0
    assert comparison["predicted_next_hour_aqi"].isna().all()
    assert comparison["anomaly_evidence"].eq("未提供異常結果").all()


def test_comparison_is_safe_for_empty_data_and_unknown_sites() -> None:
    empty = build_station_comparison(pd.DataFrame(), selected_sites=["A", "B"])
    features, predictions, anomalies = _comparison_inputs()
    unknown = build_station_comparison(features, predictions, anomalies, ["X"])

    assert empty.empty
    assert unknown.empty
    assert choose_recommended_station(empty)["site_name"] is None


def test_comparison_export_is_excel_friendly_and_excludes_internal_fields() -> None:
    features, predictions, anomalies = _comparison_inputs()
    comparison = build_station_comparison(features, predictions, anomalies, ["A", "B"])

    payload = export_comparison_csv(comparison)
    decoded = payload.decode("utf-8-sig")

    assert payload.startswith(b"\xef\xbb\xbf")
    assert "測站" in decoded
    assert "下一小時預測 AQI" in decoded
    assert "松山測站" in decoded
    assert "site_name" not in decoded
    assert "comparison_value" not in decoded

def test_comparison_includes_station_specific_prior_baseline_context() -> None:
    current = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-12 10:00", "2026-08-12 10:00"]),
            "site_name": ["A", "B"],
            "site_name_display": ["松山測站", "板橋測站"],
            "county_display": ["臺北市", "新北市"],
            "aqi": [70.0, 75.0],
            "pm25": [22.0, 28.0],
        }
    )
    reference = pd.DataFrame(
        {
            "datetime": pd.to_datetime(
                [
                    "2026-08-09 10:00",
                    "2026-08-10 10:00",
                    "2026-08-11 10:00",
                    "2026-08-09 10:00",
                    "2026-08-10 10:00",
                    "2026-08-11 10:00",
                    "2026-08-13 10:00",
                ]
            ),
            "site_name": ["A", "A", "A", "B", "B", "B", "A"],
            "site_name_display": ["松山測站"] * 3 + ["板橋測站"] * 3 + ["松山測站"],
            "county_display": ["臺北市"] * 3 + ["新北市"] * 3 + ["臺北市"],
            "aqi": [50.0, 52.0, 54.0, 80.0, 82.0, 84.0, 999.0],
            "pm25": [20.0] * 7,
        }
    )

    comparison = build_station_comparison(
        current,
        selected_sites=["A", "B"],
        reference_features=reference,
    ).set_index("site_name")

    assert comparison.loc["A", "baseline_aqi"] == 52.0
    assert comparison.loc["A", "aqi_vs_baseline"] == 18.0
    assert comparison.loc["B", "baseline_aqi"] == 82.0
    assert comparison.loc["B", "aqi_vs_baseline"] == -7.0
    assert comparison.loc["A", "context_evidence"]

def test_missing_display_labels_fall_back_without_crashing() -> None:
    features = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-12 10:00"]),
            "site_name": ["A"],
            "site_name_display": [pd.NA],
            "county_display": [pd.NA],
            "aqi": [65.0],
            "pm25": [22.0],
        }
    )

    comparison = build_station_comparison(features, selected_sites=["A"])

    assert comparison.loc[0, "site_name_display"] == "A"
    assert comparison.loc[0, "county_display"] == "未知地區"
