from __future__ import annotations

from typing import Any

import pandas as pd


def build_data_health(features: pd.DataFrame, stale_after_hours: int = 2) -> dict[str, Any]:
    """Summarize analysis readiness without relying on the wall-clock time."""
    if features.empty or "datetime" not in features:
        return {
            "status": "無資料",
            "rows": 0,
            "station_count": 0,
            "missing_cells": 0,
            "missing_rate": 0.0,
            "duplicate_station_timestamps": 0,
            "stale_station_count": 0,
            "largest_gap_hours": None,
            "latest_timestamp": None,
        }

    frame = features.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
    frame = frame.dropna(subset=["datetime"])
    station_column = "site_name" if "site_name" in frame else None
    missing_cells = int(frame.isna().sum().sum())
    total_cells = int(frame.shape[0] * frame.shape[1])
    latest_timestamp = frame["datetime"].max()
    duplicate_count = 0
    stale_station_count = 0
    largest_gap_hours: float | None = None
    if station_column:
        duplicate_count = int(frame.duplicated([station_column, "datetime"]).sum())
        station_latest = frame.groupby(station_column)["datetime"].max()
        stale_station_count = int((latest_timestamp - station_latest > pd.Timedelta(hours=stale_after_hours)).sum())
        gaps = frame.sort_values([station_column, "datetime"]).groupby(station_column)["datetime"].diff().dt.total_seconds() / 3600
        if gaps.notna().any():
            largest_gap_hours = round(float(gaps.max()), 2)

    missing_rate = round(missing_cells / total_cells, 6) if total_cells else 0.0
    if duplicate_count or stale_station_count or missing_rate > 0.05:
        status = "需留意"
    else:
        status = "可分析"
    return {
        "status": status,
        "rows": int(len(frame)),
        "station_count": int(frame[station_column].nunique()) if station_column else 0,
        "missing_cells": missing_cells,
        "missing_rate": missing_rate,
        "duplicate_station_timestamps": duplicate_count,
        "stale_station_count": stale_station_count,
        "largest_gap_hours": largest_gap_hours,
        "latest_timestamp": str(latest_timestamp),
    }
