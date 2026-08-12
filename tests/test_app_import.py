from __future__ import annotations

import importlib
import inspect
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_app_imports_without_crashing_and_theme_exists():
    app = importlib.import_module("app")
    theme = importlib.import_module("src.theme")

    assert hasattr(app, "main")
    assert hasattr(app, "inject_theme")
    assert hasattr(app, "inject_global_css")
    assert hasattr(app, "apply_plotly_theme")
    assert hasattr(app, "_build_station_map")
    assert hasattr(app, "_render_station_map")
    assert hasattr(app, "THEME")
    assert hasattr(app, "DISPLAY_COLUMN_MAP")
    assert theme.THEME
    assert theme.THEME_OPTIONS
    assert theme.DEFAULT_THEME_NAME in theme.THEME_OPTIONS
    assert all(theme.THEME[key] for key in ["primary", "background", "card", "text", "muted_text", "accent", "danger"])
    assert theme.THEME["card"].lower() != theme.THEME["text"].lower()
    assert app.DISPLAY_COLUMN_MAP["county_display"] == "縣市"
    assert app.DISPLAY_COLUMN_MAP["site_name_display"] == "測站"
    assert app.DISPLAY_COLUMN_MAP["aqi"] == "AQI"
    assert app.DISPLAY_COLUMN_MAP["timestamp"] == "時間"
    assert "available_bikes" not in app.DISPLAY_COLUMN_MAP

    required = {
        "background",
        "surface",
        "card",
        "sidebar",
        "primary",
        "secondary",
        "accent",
        "danger",
        "success",
        "warning",
        "text",
        "muted_text",
        "border",
        "table_header",
        "chart_grid",
    }
    for theme_name, option in theme.THEME_OPTIONS.items():
        assert required.issubset(option), f"{theme_name} missing keys: {required - set(option)}"
        contrast = theme.validate_theme_contrast(option)
        assert contrast["passed"], f"{theme_name} contrast failed: {contrast}"
        assert contrast["checks"]["text_vs_background"]["ratio"] >= 4.5
        assert contrast["checks"]["text_vs_card"]["ratio"] >= 4.5
        assert contrast["checks"]["muted_text_vs_background"]["ratio"] >= 3.0
        assert contrast["checks"]["muted_text_vs_card"]["ratio"] >= 3.0

    source = inspect.getsource(app.apply_plotly_theme)
    assert 'theme["card"]' in source
    assert 'theme["text"]' in source
    assert 'theme["chart_grid"]' in source
    assert theme.get_theme(theme.DEFAULT_THEME_NAME)["success_soft"].startswith("rgba(")

    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in app_source
    assert "min-height: 44px" in app_source
    assert "transition: all" not in app_source
    assert "st.json(" not in app_source
    assert "st.dataframe(" not in app_source
    assert 'role="region"' in app_source
    assert "異常事件（菱形）" in app_source
    assert "台灣 AQI 監測與預測" in app_source
    assert "環境監測資料工作台" in app_source
    assert "測站脈絡決策摘要" in app_source
    assert "台灣測站分布" in app_source
    assert 'on_select="rerun"' in app_source
    assert "build_station_risk_brief" in app_source
    assert "空氣品質活動建議" in app_source
    assert "下載目前篩選資料" in app_source
    assert "下載監測摘要" in app_source
    assert "最新資料時點" in app_source
    assert "根據目前及過去資料估計同一測站下一小時 AQI" in app_source
    assert '"地區比較"' in app_source
    assert 'max_selections=3' in app_source
    assert "目前較佳選擇" in app_source
    assert "比較結果不是官方行程或健康建議" in app_source
    assert "export_comparison_csv" in app_source
    assert "展示用途" not in app_source
    assert "background: transparent;" in app_source
    assert "box-shadow: none;" in app_source


def test_streamlit_theme_config_uses_explicit_valid_colors():
    config_source = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")

    for color_name in ["primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor"]:
        assert f'{color_name} = "#' in config_source

    assert "[theme.sidebar]" in config_source
    assert "[client]" in config_source
    assert 'toolbarMode = "minimal"' in config_source


def test_app_paths_and_missing_data_helpers_are_safe(tmp_path):
    helpers = importlib.import_module("src.app_helpers")
    missing = helpers.safe_load_csv(tmp_path / "missing.csv")
    assert missing.empty
    assert helpers.safe_load_json(tmp_path / "missing.json") == {}
    assert helpers.get_available_sites(missing) == []
    assert helpers.compute_kpis(missing, missing)["category"] == "無資料"
    assert helpers.to_chinese_location_name("Taipei") == "臺北市"
    assert helpers.to_chinese_location_name("Kaohsiung") == "高雄市"
    assert helpers.to_chinese_location_name("") == "未知地區"


def test_date_filter_does_not_include_next_day_midnight():
    helpers = importlib.import_module("src.app_helpers")
    frame = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-06-01 23:00", "2026-06-02 00:00"]),
            "site_name": ["A", "A"],
        }
    )
    filtered = helpers.filter_by_site_and_date(
        frame,
        start_datetime="2026-06-01",
        end_datetime="2026-06-01",
    )

    assert filtered["datetime"].tolist() == [pd.Timestamp("2026-06-01 23:00")]


def test_backtest_metrics_are_flattened_before_rendering():
    app = importlib.import_module("app")
    metrics = {
        "fold_count": 2,
        "aggregate": {
            "moving_average": {"mae": 6.5, "rmse": 8.4, "r2": 0.75},
            "random_forest": {"mae": 5.0, "rmse": 6.7, "r2": 0.84},
        },
    }

    table = app._backtest_aggregate_table(metrics)

    assert list(table.columns) == ["模型", "MAE", "RMSE", "R2"]
    assert table["模型"].tolist() == ["Moving Average 基準模型", "Random Forest"]
    assert not any(isinstance(value, dict) for value in table.to_numpy().ravel())


def test_confidence_metrics_are_flattened_for_dashboard():
    app = importlib.import_module("app")
    metrics = {
        "calibration_rows": 120,
        "intervals": {
            "80": {"residual_quantile": 8.5, "empirical_coverage": 0.82, "mean_width": 17.0},
            "95": {"residual_quantile": 13.0, "empirical_coverage": 0.96, "mean_width": 26.0},
        },
    }

    table = app._confidence_summary_table(metrics)

    assert list(table.columns) == ["預測區間", "校準誤差分位數", "最終測試覆蓋率", "平均區間寬度"]
    assert table["預測區間"].tolist() == ["80%", "95%"]
    assert table["最終測試覆蓋率"].tolist() == ["82.0%", "96.0%"]


def test_threshold_watch_table_prioritizes_actionable_crossings():
    app = importlib.import_module("app")
    predictions = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-01 01:00", "2026-08-01 02:00", "2026-08-01 03:00"]),
            "site_name_display": ["松山測站", "西屯測站", "前金測站"],
            "predicted_next_hour_aqi": [48.0, 95.0, 40.0],
            "upper_80_aqi": [52.0, 99.0, 45.0],
            "upper_95_aqi": [55.0, 105.0, 48.0],
            "threshold_watch_level": ["跨級關注", "不確定性關注", "區間穩定"],
            "threshold_watch_reason": ["80% 跨過 50", "95% 跨過 100", "未跨級"],
        }
    )

    table = app._threshold_watch_table(predictions)

    assert table["關注層級"].tolist() == ["跨級關注", "不確定性關注"]
    assert table["測站"].tolist() == ["松山測站", "西屯測站"]
    assert "區間穩定" not in set(table["關注層級"])

def test_confidence_table_css_can_be_injected(monkeypatch):
    app = importlib.import_module("app")

    class FakeStreamlit:
        rendered = ""

        def markdown(self, value, unsafe_allow_html=False):
            self.rendered = value

    fake_streamlit = FakeStreamlit()
    monkeypatch.setattr(app, "st", fake_streamlit)

    app.inject_global_css(app.THEME)

    assert ".confidence-watch-table" in fake_streamlit.rendered
    assert "min-width: 6.5rem" in fake_streamlit.rendered

def test_threshold_watch_cards_keep_context_without_raw_table_markup():
    app = importlib.import_module("app")
    table = pd.DataFrame(
        {
            "時間": [pd.Timestamp("2026-08-01 01:00")],
            "測站": ["松山測站"],
            "預測 AQI": [48.2],
            "80% 上界": [52.0],
            "95% 上界": [55.0],
            "關注層級": ["跨級關注"],
            "判讀依據": ["80% 預測區間上界跨過 AQI 50"],
        }
    )

    html = app._threshold_watch_cards_html(table)

    assert "松山測站" in html
    assert "08/01 01:00" in html
    assert "48.2" in html
    assert "80% 預測區間上界跨過 AQI 50" in html
    assert "<table" not in html


def test_comparison_cards_are_escaped_and_keep_decision_context():
    app = importlib.import_module("app")
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
            "forecast_change": [-3.0],
            "is_anomaly": [False],
        }
    )

    html = app.comparison_cards_html(comparison)

    assert "松山&lt;script&gt;" in html
    assert "目前 AQI" in html
    assert "下一小時" in html
    assert "56.0–68.0" in html
    assert "08/12 10:00" in html
    assert "<script>" not in html
    assert 'class="comparison-grid"' in html


def test_comparison_css_is_responsive_and_high_contrast(monkeypatch):
    app = importlib.import_module("app")

    class FakeStreamlit:
        rendered = ""

        def markdown(self, value, unsafe_allow_html=False):
            self.rendered = value

    fake_streamlit = FakeStreamlit()
    monkeypatch.setattr(app, "st", fake_streamlit)

    app.inject_global_css(app.THEME)

    assert ".comparison-grid" in fake_streamlit.rendered
    assert ".comparison-card" in fake_streamlit.rendered
    assert "grid-template-columns: 1fr" in fake_streamlit.rendered
    assert "flex-wrap: wrap" in fake_streamlit.rendered
    assert "flex: 1 1 calc(33.333%" in fake_streamlit.rendered
