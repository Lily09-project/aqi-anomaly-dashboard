from __future__ import annotations

import pandas as pd

from src.dashboard.context import DashboardData, FilterState
from src.dashboard.data_service import build_filtered_data


def _source() -> DashboardData:
    frame = pd.DataFrame(
        {
            "datetime": pd.to_datetime(
                ["2026-08-10 10:00", "2026-08-10 10:00", "2026-08-11 10:00"]
            ),
            "site_name": ["A", "B", "A"],
            "site_name_display": ["A站", "B站", "A站"],
            "county_display": ["北市", "中市", "北市"],
            "aqi": [50.0, 60.0, 70.0],
        }
    )
    return DashboardData(frame, frame.copy(), frame.copy(), frame.copy())


def test_filter_scopes_have_distinct_semantics() -> None:
    filtered = build_filtered_data(
        _source(),
        FilterState(
            county="北市",
            site_name="A",
            site_display="A站",
            start_date=pd.Timestamp("2026-08-10").date(),
            end_date=pd.Timestamp("2026-08-10").date(),
        ),
    )

    assert filtered.selected.features["site_name"].tolist() == ["A"]
    assert filtered.regional.features["county_display"].tolist() == ["北市"]
    assert set(filtered.comparison.features["site_name"]) == {"A", "B"}
    assert filtered.source.features.shape[0] == 3
