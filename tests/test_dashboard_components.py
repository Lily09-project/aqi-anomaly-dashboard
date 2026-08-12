from __future__ import annotations

import importlib

import pandas as pd

from src.dashboard import components


def test_component_comparison_cards_escape_data_values() -> None:
    comparison = pd.DataFrame(
        {
            "site_name_display": ["松山<script>"],
            "county_display": ["臺北市"],
            "observed_at": [pd.Timestamp("2026-08-12 10:00")],
            "freshness_state": ["可比較"],
            "current_aqi": [65.0],
            "aqi_category": ["普通"],
            "pm25": [22.0],
            "predicted_next_hour_aqi": [62.0],
            "lower_80_aqi": [56.0],
            "upper_80_aqi": [68.0],
            "is_anomaly": [False],
        }
    )

    html = components.comparison_cards_html(comparison)

    assert "松山&lt;script&gt;" in html
    assert "<script>" not in html


def test_component_model_metrics_table_flattens_named_models() -> None:
    table = components.model_metrics_table(
        {"model_comparison": {"linear_regression": {"mae": 5.1, "rmse": 7.2, "r2": 0.8}}}
    )

    assert table.to_dict("records") == [
        {"模型": "Linear Regression", "MAE": 5.1, "RMSE": 7.2, "R2": 0.8}
    ]


def test_app_reexports_component_contracts() -> None:
    app = importlib.import_module("app")

    assert app.comparison_cards_html is components.comparison_cards_html
    assert app.apply_plotly_theme is components.apply_plotly_theme
