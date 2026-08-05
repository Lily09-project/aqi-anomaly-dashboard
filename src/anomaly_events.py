from __future__ import annotations

from typing import Any

import pandas as pd

from src.risk_brief import describe_anomaly_evidence


EVENT_COLUMNS = [
    "event_id",
    "datetime",
    "end_datetime",
    "site_name",
    "site_name_display",
    "county_display",
    "event_points",
    "duration_hours",
    "peak_datetime",
    "peak_aqi",
    "peak_pm25",
    "max_anomaly_score",
    "evidence_summary",
]


def _empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_COLUMNS)


def _event_evidence(rows: pd.DataFrame) -> str:
    labels: list[str] = []
    for _, row in rows.iterrows():
        for label in describe_anomaly_evidence(row).split("、"):
            if label and label != "未達異常旗標" and label not in labels:
                labels.append(label)
    return "、".join(labels) if labels else "異常模型標記"


def build_anomaly_events(anomalies: pd.DataFrame, max_gap_hours: int = 1) -> pd.DataFrame:
    """Merge adjacent anomaly observations into station-specific investigation events."""
    required = {"datetime", "site_name", "aqi", "is_anomaly"}
    if anomalies.empty or not required.issubset(anomalies.columns):
        return _empty_events()

    flagged = anomalies.copy()
    flagged["datetime"] = pd.to_datetime(flagged["datetime"], errors="coerce")
    flagged["aqi"] = pd.to_numeric(flagged["aqi"], errors="coerce")
    flagged["pm25"] = (
        pd.to_numeric(flagged["pm25"], errors="coerce") if "pm25" in flagged else pd.NA
    )
    flagged["anomaly_score"] = (
        pd.to_numeric(flagged["anomaly_score"], errors="coerce")
        if "anomaly_score" in flagged
        else pd.NA
    )
    flagged = flagged[(pd.to_numeric(flagged["is_anomaly"], errors="coerce") == 1)].dropna(
        subset=["datetime", "site_name", "aqi"]
    )
    if flagged.empty:
        return _empty_events()

    rows: list[dict[str, Any]] = []
    max_gap = pd.Timedelta(hours=max(1, int(max_gap_hours)))
    for site_name, station_rows in flagged.groupby("site_name", sort=False):
        station_rows = station_rows.sort_values("datetime").copy()
        station_rows["event_group"] = station_rows["datetime"].diff().gt(max_gap).cumsum()
        for _, event_rows in station_rows.groupby("event_group", sort=False):
            start = pd.Timestamp(event_rows["datetime"].min())
            end = pd.Timestamp(event_rows["datetime"].max())
            peak_index = event_rows["aqi"].idxmax()
            peak_row = event_rows.loc[peak_index]
            rows.append(
                {
                    "event_id": f"{site_name}-{start:%Y%m%d%H}",
                    "datetime": start,
                    "end_datetime": end,
                    "site_name": str(site_name),
                    "site_name_display": str(peak_row.get("site_name_display", site_name)),
                    "county_display": str(peak_row.get("county_display", "未知地區")),
                    "event_points": int(len(event_rows)),
                    "duration_hours": int((end - start) / pd.Timedelta(hours=1)) + 1,
                    "peak_datetime": pd.Timestamp(peak_row["datetime"]),
                    "peak_aqi": round(float(peak_row["aqi"]), 1),
                    "peak_pm25": round(float(peak_row["pm25"]), 1) if pd.notna(peak_row["pm25"]) else None,
                    "max_anomaly_score": round(float(event_rows["anomaly_score"].max()), 3)
                    if event_rows["anomaly_score"].notna().any()
                    else None,
                    "evidence_summary": _event_evidence(event_rows),
                }
            )
    return pd.DataFrame(rows, columns=EVENT_COLUMNS).sort_values(
        ["max_anomaly_score", "peak_aqi", "datetime"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)
