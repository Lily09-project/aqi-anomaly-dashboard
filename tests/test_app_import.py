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
    assert app.DISPLAY_COLUMN_MAP["station_name"] == "站點名稱"

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
    assert "展示用途" not in app_source
    assert "background: transparent;" in app_source
    assert "box-shadow: none;" in app_source


def test_streamlit_theme_config_uses_explicit_valid_colors():
    config_source = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")

    for color_name in ["primaryColor", "backgroundColor", "secondaryBackgroundColor", "textColor"]:
        assert f'{color_name} = "#' in config_source

    assert "[theme.sidebar]" in config_source


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
