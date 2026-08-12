from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.forecast_confidence import (
    apply_prediction_intervals,
    build_confidence_metrics,
    build_group_coverage,
    calibrate_interval_widths,
    classify_threshold_watch,
)


def test_calibration_is_monotonic_and_intervals_are_non_negative():
    widths = calibrate_interval_widths(range(1, 11), levels=(0.8, 0.95))

    result = apply_prediction_intervals(
        pd.DataFrame({"prediction": [2.0, 100.0]}),
        prediction_col="prediction",
        widths=widths,
    )

    assert widths["95"] >= widths["80"] >= 0
    assert (result["lower_95_aqi"] >= 0).all()
    assert (result["lower_95_aqi"] <= result["lower_80_aqi"]).all()
    assert (result["upper_95_aqi"] >= result["upper_80_aqi"]).all()


def test_calibration_rejects_too_few_finite_residuals():
    with pytest.raises(ValueError, match="at least two finite"):
        calibrate_interval_widths([math.nan, 2.0, math.inf])


def test_threshold_watch_distinguishes_80_and_95_percent_crossings():
    frame = pd.DataFrame(
        {
            "predicted_next_hour_aqi": [48.0, 48.0, 40.0, 105.0],
            "upper_80_aqi": [52.0, 49.0, 45.0, 120.0],
            "upper_95_aqi": [55.0, 53.0, 48.0, 152.0],
        }
    )

    result = classify_threshold_watch(frame, thresholds=[50, 100, 150])

    assert result["threshold_watch_level"].tolist() == [
        "跨級關注",
        "不確定性關注",
        "區間穩定",
        "不確定性關注",
    ]
    assert result.loc[0, "next_aqi_threshold"] == 50
    assert "80%" in result.loc[0, "threshold_watch_reason"]
    assert "95%" in result.loc[1, "threshold_watch_reason"]


def test_confidence_metrics_report_empirical_coverage_without_recalibration():
    frame = pd.DataFrame(
        {
            "actual_next_hour_aqi": [45.0, 50.0, 60.0, 80.0],
            "lower_80_aqi": [40.0, 48.0, 55.0, 60.0],
            "upper_80_aqi": [50.0, 52.0, 65.0, 75.0],
            "lower_95_aqi": [35.0, 45.0, 50.0, 55.0],
            "upper_95_aqi": [55.0, 55.0, 70.0, 85.0],
        }
    )
    widths = {"80": 5.0, "95": 10.0}

    metrics = build_confidence_metrics(
        frame,
        widths=widths,
        calibration_rows=120,
        calibration_period={"start": "2026-01-01", "end": "2026-01-20"},
        final_test_period={"start": "2026-01-21", "end": "2026-01-30"},
        thresholds=[50, 100, 150],
    )

    assert metrics["method"] == "rolling_origin_conformal"
    assert metrics["calibration_rows"] == 120
    assert metrics["intervals"]["80"]["empirical_coverage"] == 0.75
    assert metrics["intervals"]["95"]["empirical_coverage"] == 1.0
    assert metrics["intervals"]["80"]["mean_width"] == 9.75
    assert metrics["calibration_period"]["end"] < metrics["final_test_period"]["start"]


def test_group_coverage_reports_known_station_outcomes_and_small_groups() -> None:
    frame = pd.DataFrame(
        {
            "site_name_display": ["站 A", "站 A", "站 B"],
            "actual_next_hour_aqi": [10.0, 20.0, 30.0],
            "lower_80_aqi": [8.0, 21.0, 25.0],
            "upper_80_aqi": [12.0, 25.0, 35.0],
            "lower_95_aqi": [5.0, 15.0, 20.0],
            "upper_95_aqi": [15.0, 25.0, 40.0],
        }
    )
    report = build_group_coverage(frame, "site_name_display", levels=(0.8, 0.95))
    by_station = {row["station"]: row for row in report["groups"]}

    assert report["group_column"] == "site_name_display"
    assert by_station["站 A"]["rows"] == 2
    assert by_station["站 A"]["intervals"]["80"]["rows"] == 2
    assert by_station["站 A"]["intervals"]["80"]["empirical_coverage"] == 0.5
    assert by_station["站 A"]["intervals"]["95"]["empirical_coverage"] == 1.0
    assert by_station["站 B"]["rows"] == 1