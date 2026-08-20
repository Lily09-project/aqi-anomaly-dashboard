from __future__ import annotations

import pandas as pd

from src.train_predictor import build_monitoring_predictions


def test_build_monitoring_predictions_combines_auditable_scored_windows() -> None:
    oof_rows = [
        {
            "datetime": "2026-08-01 01:00:00",
            "site_name": "station-a",
            "county": "County A",
            "target_next_hour_aqi": 52.0,
            "pred_linear_regression": 50.0,
            "training_cutoff": "2026-07-31 23:00:00",
        },
        {
            "datetime": "2026-08-01 02:00:00",
            "site_name": "station-a",
            "county": "County A",
            "target_next_hour_aqi": 54.0,
            "pred_linear_regression": 53.0,
            "training_cutoff": "2026-08-01 00:00:00",
        },
    ]
    final_test = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-02 01:00:00"]),
            "site_name": ["station-a"],
            "county": ["County A"],
            "actual_next_hour_aqi": [58.0],
            "pred_linear_regression": [56.0],
            "training_cutoff": pd.to_datetime(["2026-08-02 00:00:00"]),
        }
    )

    result = build_monitoring_predictions(
        oof_rows,
        final_test,
        preferred_model="linear_regression",
        interval_widths={"80": 4.0, "95": 8.0},
    )

    assert set(result["prediction_stage"]) == {"rolling_origin_oof", "final_test"}
    assert len(result) == 3
    assert {"lower_80_aqi", "upper_80_aqi", "lower_95_aqi", "upper_95_aqi"}.issubset(result.columns)
    assert result["training_cutoff"].notna().all()
    assert (result["training_cutoff"] < result["datetime"]).all()
    assert result["predicted_next_hour_aqi"].tolist() == [50.0, 53.0, 56.0]


def test_build_monitoring_predictions_rejects_missing_model_prediction() -> None:
    final_test = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-02 01:00:00"]),
            "site_name": ["station-a"],
            "actual_next_hour_aqi": [58.0],
            "training_cutoff": pd.to_datetime(["2026-08-02 00:00:00"]),
        }
    )

    try:
        build_monitoring_predictions(
            [],
            final_test,
            preferred_model="linear_regression",
            interval_widths={"80": 4.0, "95": 8.0},
        )
    except ValueError as exc:
        assert "pred_linear_regression" in str(exc)
    else:
        raise AssertionError("Missing preferred-model predictions must fail clearly")
