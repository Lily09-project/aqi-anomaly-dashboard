from __future__ import annotations

import pandas as pd

from src.model_reliability import build_reliability_report


def _predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "site_name_display": ["站 A", "站 A", "站 B", "站 B", "站 C"],
            "actual_next_hour_aqi": [10.0, 20.0, 100.0, 110.0, float("nan")],
            "predicted_next_hour_aqi": [12.0, 18.0, 90.0, 100.0, 1.0],
            "pred_moving_average": [15.0, 25.0, 120.0, 130.0, 1.0],
        }
    )


def test_reliability_report_has_station_band_and_row_counts() -> None:
    report = build_reliability_report(_predictions())

    assert report["overall"]["rows"] == 4
    assert {row["station"] for row in report["by_station"]} == {"站 A", "站 B"}
    assert all(row["rows"] == 2 for row in report["by_station"])
    assert sum(row["rows"] for row in report["by_aqi_band"]) == 4
    assert all("rows" in row for row in report["by_aqi_band"])


def test_reliability_report_quantifies_baseline_improvement_and_worst_station() -> None:
    report = build_reliability_report(_predictions())
    improvement = report["baseline_improvement"]

    assert improvement["rows"] == 4
    assert improvement["model_mae"] < improvement["baseline_mae"]
    assert improvement["mae_reduction"] > 0
    assert improvement["mae_reduction_pct"] > 0
    assert report["worst_station"]["station"] == "站 B"
    assert report["worst_station"]["rows"] == 2