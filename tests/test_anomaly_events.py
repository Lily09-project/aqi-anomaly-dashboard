from __future__ import annotations

import pandas as pd

from src.anomaly_events import EVENT_COLUMNS, build_anomaly_events


def test_build_anomaly_events_keeps_station_boundaries_and_merges_adjacent_rows() -> None:
    anomalies = pd.DataFrame(
        {
            "datetime": pd.to_datetime(
                ["2026-01-01 10:00", "2026-01-01 11:00", "2026-01-01 14:00", "2026-01-01 11:00"]
            ),
            "site_name": ["A", "A", "A", "B"],
            "site_name_display": ["A", "A", "A", "B"],
            "county_display": ["North", "North", "North", "South"],
            "aqi": [80, 125, 95, 110],
            "pm25": [20, 48, 30, 40],
            "anomaly_score": [0.34, 1.0, 0.67, 0.67],
            "is_anomaly": [1, 1, 1, 1],
            "pseudo_anomaly": [0, 1, 0, 1],
            "zscore_anomaly": [1, 1, 1, 0],
            "isolation_forest_anomaly": [0, 1, 0, 1],
        }
    )

    events = build_anomaly_events(anomalies, max_gap_hours=1)

    assert len(events) == 3
    station_a_first = events[(events["site_name"] == "A") & (events["event_points"] == 2)].iloc[0]
    assert station_a_first["duration_hours"] == 2
    assert station_a_first["peak_aqi"] == 125.0
    assert station_a_first["peak_pm25"] == 48.0
    assert "偏離近期分布" in station_a_first["evidence_summary"]
    assert (events["site_name"] == "B").sum() == 1


def test_build_anomaly_events_returns_stable_empty_schema() -> None:
    events = build_anomaly_events(pd.DataFrame({"datetime": [], "site_name": [], "aqi": [], "is_anomaly": []}))

    assert events.empty
    assert list(events.columns) == EVENT_COLUMNS
