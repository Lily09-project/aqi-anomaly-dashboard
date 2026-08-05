from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app_helpers import get_station_coordinates
from src.risk_brief import build_station_risk_brief, describe_anomaly_evidence


def _risk_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    as_of = pd.Timestamp("2026-07-15 12:00")
    history = pd.DataFrame(
        {
            "datetime": [
                "2026-07-01 12:00",
                "2026-07-02 12:00",
                "2026-07-03 12:00",
                "2026-07-01 11:00",
                "2026-07-02 11:00",
                "2026-07-03 11:00",
                "2026-07-01 12:00",
                "2026-07-02 12:00",
                "2026-07-03 12:00",
                "2026-07-01 11:00",
                "2026-07-02 11:00",
                "2026-07-03 11:00",
                "2026-07-20 12:00",
            ],
            "site_name": ["A"] * 6 + ["B"] * 6 + ["A"],
            "site_name_display": ["松山測站"] * 6 + ["板橋測站"] * 6 + ["松山測站"],
            "county_display": ["臺北市"] * 6 + ["新北市"] * 6 + ["臺北市"],
            "aqi": [20, 21, 19, 18, 20, 19, 80, 79, 81, 78, 80, 82, 999],
            "pm25": [10] * 6 + [30] * 6 + [90],
        }
    )
    history["datetime"] = pd.to_datetime(history["datetime"])
    current = pd.DataFrame(
        {
            "datetime": [as_of, as_of],
            "site_name": ["A", "B"],
            "site_name_display": ["松山測站", "板橋測站"],
            "county_display": ["臺北市", "新北市"],
            "aqi": [100, 85],
            "pm25": [42, 30],
        }
    )
    predictions = pd.DataFrame(
        {
            "datetime": [as_of, as_of],
            "site_name": ["A", "B"],
            "predicted_next_hour_aqi": [112, 86],
        }
    )
    anomalies = pd.DataFrame(
        {
            "datetime": [as_of, as_of],
            "site_name": ["A", "B"],
            "is_anomaly": [1, 0],
            "anomaly_score": [1.0, 0.0],
            "pseudo_anomaly": [1, 0],
            "zscore_anomaly": [1, 0],
            "isolation_forest_anomaly": [1, 0],
        }
    )
    return current, history, predictions, anomalies


def test_station_risk_brief_uses_only_prior_same_station_history():
    current, history, predictions, anomalies = _risk_inputs()
    brief = build_station_risk_brief(current, history, predictions, anomalies)

    aqi_a = brief.set_index("site_name").loc["A"]
    aqi_b = brief.set_index("site_name").loc["B"]
    assert aqi_a["baseline_aqi"] == 20.0
    assert aqi_b["baseline_aqi"] == 80.0
    assert aqi_a["aqi_vs_baseline"] == 80.0
    assert aqi_b["aqi_vs_baseline"] == 5.0
    assert aqi_a["predicted_next_hour_aqi"] == 112.0
    assert aqi_a["priority_score"] > aqi_b["priority_score"]
    assert brief.iloc[0]["site_name"] == "A"


def test_risk_brief_handles_missing_optional_sources_and_keeps_disclaimer_fields():
    current, history, _, _ = _risk_inputs()
    brief = build_station_risk_brief(current, history)

    assert len(brief) == 2
    assert brief["predicted_next_hour_aqi"].isna().all()
    assert brief["anomaly_flag"].eq(0).all()
    assert brief["evidence_summary"].str.len().gt(0).all()


def test_anomaly_evidence_and_station_coordinates_are_human_readable():
    evidence = describe_anomaly_evidence(
        pd.Series({"pseudo_anomaly": 1, "zscore_anomaly": 1, "isolation_forest_anomaly": 1})
    )
    assert evidence == "達到規則門檻、偏離近期分布、多變量型態偏離"
    assert get_station_coordinates("松山測站", "臺北市") == (25.05, 121.548)
    assert get_station_coordinates("未知站", "臺北市") == (25.033, 121.565)
