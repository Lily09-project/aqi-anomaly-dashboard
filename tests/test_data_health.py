from __future__ import annotations

import pandas as pd

from src.data_health import build_data_health


def test_data_health_reports_analyzable_complete_station_data() -> None:
    frame = pd.DataFrame(
        {
            "datetime": pd.to_datetime(
                ["2026-01-01 00:00", "2026-01-01 01:00", "2026-01-01 00:00", "2026-01-01 01:00"]
            ),
            "site_name": ["A", "A", "B", "B"],
            "aqi": [40, 42, 45, 43],
        }
    )

    health = build_data_health(frame)

    assert health["status"] == "可分析"
    assert health["duplicate_station_timestamps"] == 0
    assert health["stale_station_count"] == 0
    assert health["largest_gap_hours"] == 1.0


def test_data_health_flags_duplicates_and_stale_stations() -> None:
    frame = pd.DataFrame(
        {
            "datetime": pd.to_datetime(
                ["2026-01-01 00:00", "2026-01-01 03:00", "2026-01-01 03:00", "2026-01-01 00:00"]
            ),
            "site_name": ["A", "A", "A", "B"],
            "aqi": [40, 42, 42, 45],
        }
    )

    health = build_data_health(frame, stale_after_hours=2)

    assert health["status"] == "需留意"
    assert health["duplicate_station_timestamps"] == 1
    assert health["stale_station_count"] == 1
    assert health["largest_gap_hours"] == 3.0


def test_data_health_handles_missing_data() -> None:
    health = build_data_health(pd.DataFrame())

    assert health["status"] == "無資料"
    assert health["rows"] == 0
