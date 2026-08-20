from __future__ import annotations

from typing import Any, Mapping

import pandas as pd


def _parse_timestamp(value: object) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return pd.Timestamp(parsed)


def _elapsed_hours(timestamp: pd.Timestamp | None) -> float | None:
    if timestamp is None:
        return None
    now = pd.Timestamp.now(tz="UTC")
    return max(0.0, (now - timestamp).total_seconds() / 3600)


def _source_health(source_metadata: Mapping[str, Any] | None, latest_timestamp: pd.Timestamp | None, stale_after_hours: int) -> dict[str, Any]:
    metadata = source_metadata or {}
    source_status = str(metadata.get("status", "unknown"))
    fetched_at = _parse_timestamp(metadata.get("fetched_at_utc"))
    source_age = _elapsed_hours(fetched_at)
    source_is_stale = bool(
        source_status == "success"
        and source_age is not None
        and source_age > stale_after_hours
        and metadata.get("data_source") == "API Data"
    )
    latest_observation = _parse_timestamp(latest_timestamp)
    observation_delay = _elapsed_hours(latest_observation)
    observation_is_stale = bool(
        source_status == "success"
        and metadata.get("data_source") == "API Data"
        and observation_delay is not None
        and observation_delay > stale_after_hours
    )
    return {
        "source_status": source_status,
        "provider": metadata.get("provider", "unknown"),
        "data_source": metadata.get("data_source", "Unknown"),
        "is_simulated_data": bool(metadata.get("is_simulated_data", False)),
        "requested_at_utc": metadata.get("requested_at_utc"),
        "fetched_at_utc": metadata.get("fetched_at_utc"),
        "source_age_hours": None if source_age is None else round(source_age, 2),
        "source_is_stale": source_is_stale,
        "latest_observation": None if latest_timestamp is None else str(latest_timestamp),
        "observation_delay_hours": None if observation_delay is None else round(observation_delay, 2),
        "observation_is_stale": observation_is_stale,
        "fallback_reason": metadata.get("fallback_reason"),
    }


def build_data_health(
    features: pd.DataFrame,
    stale_after_hours: int = 2,
    source_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize analysis readiness and distinguish source from observation freshness."""
    if features.empty or "datetime" not in features:
        result = {
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
        result.update(_source_health(source_metadata, None, stale_after_hours))
        return result

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
    source_fields = _source_health(source_metadata, latest_timestamp, stale_after_hours)
    if duplicate_count or stale_station_count or missing_rate > 0.05 or source_fields["source_is_stale"] or source_fields["observation_is_stale"]:
        status = "需留意"
    else:
        status = "可分析"
    result = {
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
    result.update(source_fields)
    return result