from __future__ import annotations

from pathlib import Path

import pytest

from src.dashboard.context import (
    DashboardData,
    DashboardMetrics,
    FilteredData,
    FilterState,
    PageContext,
)
from src.dashboard.pages import PAGE_RENDERERS


EXPECTED_PAGES = {"總覽", "地區比較", "預測", "異常偵測", "資料品質", "模型指標"}


def _empty_context() -> PageContext:
    empty = DashboardData.empty()
    return PageContext(
        data=FilteredData(source=empty, selected=empty, regional=DashboardData.empty(), comparison=DashboardData.empty()),
        metrics=DashboardMetrics.empty(),
        filters=FilterState(None, None, "全部測站", None, None),
        theme={
            "primary": "#3966A2",
            "secondary": "#6191D3",
            "accent": "#E86349",
            "danger": "#E86349",
            "text": "#F8F6F6",
            "muted_text": "#D6DFEB",
            "card": "#132843",
            "surface": "#252C38",
            "background": "#0B1424",
            "border": "#3966A2",
            "chart_grid": "#3966A2",
        },
        config={},
        source_code="Sample Data",
        data_source="Sample Data",
    )


def test_all_six_page_renderers_are_registered() -> None:
    assert set(PAGE_RENDERERS) == EXPECTED_PAGES
    assert all(callable(renderer) for renderer in PAGE_RENDERERS.values())


def test_page_modules_do_not_read_artifacts() -> None:
    page_root = Path(__file__).parents[1] / "src" / "dashboard" / "pages"
    forbidden = ("read_csv(", "load_config(", "load_model(", "load_metrics(")

    for path in page_root.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in source, f"{path.name} contains {token}"


def test_overview_empty_state_is_explicit(monkeypatch) -> None:
    from src.dashboard.pages import overview

    messages: list[str] = []

    class FakeStreamlit:
        def info(self, value: str) -> None:
            messages.append(value)

    monkeypatch.setattr(overview, "st", FakeStreamlit())
    overview.render(_empty_context())

    assert messages == ["目前篩選條件下沒有 AQI 資料。"]


@pytest.mark.parametrize("label", sorted(EXPECTED_PAGES))
def test_registered_renderers_accept_page_context(label: str) -> None:
    assert PAGE_RENDERERS[label].__annotations__["context"] is PageContext


def test_metrics_page_builds_reliability_tables_without_raw_json() -> None:
    from src.dashboard.pages.metrics import reliability_station_table, station_coverage_table

    predictor = {
        "reliability": {
            "by_station": [{"station": "站 A", "rows": 12, "mae": 3.0, "rmse": 4.0, "r2": 0.8}],
            "worst_station": {"station": "站 A", "rows": 12, "rmse": 4.0},
            "baseline_improvement": {"rows": 12, "mae_reduction_pct": 10.0},
        }
    }
    confidence = {
        "station_coverage": {
            "groups": [
                {
                    "station": "站 A",
                    "rows": 12,
                    "intervals": {
                        "80": {"rows": 12, "empirical_coverage": 0.75, "mean_width": 10.0},
                        "95": {"rows": 12, "empirical_coverage": 1.0, "mean_width": 20.0},
                    },
                }
            ]
        }
    }

    reliability_table = reliability_station_table(predictor)
    coverage_table = station_coverage_table(confidence)
    source = (Path(__file__).parents[1] / "src" / "dashboard" / "pages" / "metrics.py").read_text(encoding="utf-8")

    assert reliability_table.loc[0, "rows"] == 12
    assert coverage_table.loc[0, "coverage_80"] == 0.75
    assert coverage_table.loc[0, "rows_95"] == 12
    assert "baseline_improvement" in source
    assert "worst_station" in source
    assert "st.json" not in source