from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


class DataContractError(ValueError):
    """Raised when a dashboard data scope lacks required columns."""


@dataclass(frozen=True)
class DashboardData:
    features: pd.DataFrame
    predictions: pd.DataFrame
    anomalies: pd.DataFrame
    events: pd.DataFrame

    @classmethod
    def empty(cls) -> "DashboardData":
        return cls(
            features=pd.DataFrame(),
            predictions=pd.DataFrame(),
            anomalies=pd.DataFrame(),
            events=pd.DataFrame(),
        )


@dataclass(frozen=True)
class FilteredData:
    source: DashboardData
    selected: DashboardData
    regional: DashboardData
    comparison: DashboardData


@dataclass(frozen=True)
class DashboardMetrics:
    predictor: dict[str, Any]
    anomaly: dict[str, Any]
    backtest: dict[str, Any]
    confidence: dict[str, Any]
    data_health: dict[str, Any]
    evaluation: dict[str, Any]
    manifest: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "DashboardMetrics":
        return cls(
            predictor={},
            anomaly={},
            backtest={},
            confidence={},
            data_health={},
            evaluation={},
            manifest={},
        )


@dataclass(frozen=True)
class FilterState:
    county: str | None
    site_name: str | None
    site_display: str
    start_date: Any | None
    end_date: Any | None


@dataclass(frozen=True)
class PageContext:
    data: FilteredData
    metrics: DashboardMetrics
    filters: FilterState
    theme: dict[str, str]
    config: dict[str, Any]
    source_code: str
    data_source: str

    def validate_selected_features(self, required: set[str]) -> None:
        missing = sorted(required - set(self.data.selected.features.columns))
        if missing:
            raise DataContractError(
                "Selected feature data is missing required columns: " + ", ".join(missing)
            )
