from __future__ import annotations

import pandas as pd
import pytest

from src.dashboard.context import (
    DashboardData,
    DashboardMetrics,
    DataContractError,
    FilteredData,
    FilterState,
    PageContext,
)


def _context(features: pd.DataFrame) -> PageContext:
    selected = DashboardData(
        features=features,
        predictions=pd.DataFrame(),
        anomalies=pd.DataFrame(),
        events=pd.DataFrame(),
    )
    return PageContext(
        data=FilteredData(source=selected, selected=selected, regional=DashboardData.empty(), comparison=DashboardData.empty()),
        metrics=DashboardMetrics.empty(),
        filters=FilterState(
            county=None,
            site_name=None,
            site_display="全部測站",
            start_date=None,
            end_date=None,
        ),
        theme={"text": "#ffffff"},
        config={},
        source_code="Sample Data",
        data_source="Sample Data",
    )


def test_dashboard_data_empty_returns_independent_frames() -> None:
    first = DashboardData.empty()
    second = DashboardData.empty()

    assert first.features.empty
    assert first.predictions.empty
    assert first.anomalies.empty
    assert first.events.empty
    assert first.features is not first.predictions
    assert first.features is not second.features


def test_dashboard_metrics_empty_has_all_named_reports() -> None:
    metrics = DashboardMetrics.empty()

    assert metrics.predictor == {}
    assert metrics.anomaly == {}
    assert metrics.backtest == {}
    assert metrics.confidence == {}
    assert metrics.data_health == {}
    assert metrics.evaluation == {}
    assert metrics.manifest == {}
    assert metrics.monitoring == {}


def test_page_context_validates_required_selected_columns() -> None:
    context = _context(pd.DataFrame({"aqi": [65.0]}))

    with pytest.raises(DataContractError, match="datetime"):
        context.validate_selected_features({"datetime", "aqi"})


def test_page_context_accepts_complete_selected_columns() -> None:
    context = _context(
        pd.DataFrame(
            {
                "datetime": pd.to_datetime(["2026-08-12 10:00"]),
                "site_name": ["A"],
                "aqi": [65.0],
            }
        )
    )

    context.validate_selected_features({"datetime", "site_name", "aqi"})
