from __future__ import annotations

import pandas as pd

from src.monitoring import build_monitoring_report


def _features(current_shift: float = 0.0) -> pd.DataFrame:
    timestamps = pd.date_range("2026-08-01", periods=24 * 21, freq="h")
    frame = pd.DataFrame(
        {
            "datetime": timestamps,
            "site_name": "station-a",
            "aqi": 50.0,
            "pm25": 20.0,
        }
    )
    current_start = timestamps.max() - pd.Timedelta(days=7) + pd.Timedelta(hours=1)
    current = frame["datetime"] >= current_start
    frame.loc[current, "aqi"] += current_shift
    frame.loc[current, "pm25"] += current_shift / 2
    return frame


def _predictions(current_error: float = 2.0) -> pd.DataFrame:
    timestamps = pd.date_range("2026-08-01", periods=24 * 21, freq="h")
    frame = pd.DataFrame(
        {
            "datetime": timestamps,
            "actual_next_hour_aqi": 50.0,
            "predicted_next_hour_aqi": 48.0,
            "lower_80_aqi": 45.0,
            "upper_80_aqi": 55.0,
            "lower_95_aqi": 40.0,
            "upper_95_aqi": 60.0,
        }
    )
    current_start = timestamps.max() - pd.Timedelta(days=7) + pd.Timedelta(hours=1)
    current = frame["datetime"] >= current_start
    frame.loc[current, "predicted_next_hour_aqi"] = 50.0 - current_error
    return frame


def test_monitoring_report_uses_non_overlapping_chronological_windows() -> None:
    report = build_monitoring_report(_features(), _predictions())

    assert report["status"] == "stable"
    assert report["reference_window"]["rows"] == 24 * 14
    assert report["current_window"]["rows"] == 24 * 7
    assert report["reference_window"]["end"] < report["current_window"]["start"]
    assert report["retraining"]["recommended"] is False


def test_monitoring_report_flags_distribution_and_prediction_drift() -> None:
    report = build_monitoring_report(
        _features(current_shift=30.0),
        _predictions(current_error=12.0),
        thresholds={"mean_shift_warning": 0.5, "mean_shift_critical": 1.0, "mae_increase_warning_pct": 25.0},
    )

    signals = {item["column"]: item for item in report["signals"]}
    assert report["status"] in {"warning", "critical"}
    assert signals["aqi"]["status"] == "critical"
    assert signals["pm25"]["status"] == "critical"
    assert report["prediction"]["reference_mae"] == 2.0
    assert report["prediction"]["current_mae"] == 12.0
    assert report["prediction"]["mae_change_pct"] == 500.0
    assert report["prediction"]["status"] == "critical"
    assert report["retraining"]["recommended"] is True
    assert report["retraining"]["reasons"]


def test_monitoring_report_calculates_interval_coverage() -> None:
    predictions = _predictions()
    current_start = predictions["datetime"].max() - pd.Timedelta(days=7) + pd.Timedelta(hours=1)
    predictions.loc[predictions["datetime"] >= current_start, "upper_80_aqi"] = 49.0

    report = build_monitoring_report(_features(), predictions)

    assert report["coverage"]["80"]["reference"] == 1.0
    assert report["coverage"]["80"]["current"] == 0.0
    assert report["coverage"]["80"]["status"] == "critical"
    assert report["coverage"]["95"]["current"] == 1.0


def test_monitoring_report_handles_empty_or_short_data() -> None:
    empty = build_monitoring_report(pd.DataFrame(), pd.DataFrame())
    short = build_monitoring_report(_features().tail(24), _predictions().tail(24))

    assert empty["status"] == "insufficient_data"
    assert short["status"] == "insufficient_data"
    assert empty["retraining"]["recommended"] is False
