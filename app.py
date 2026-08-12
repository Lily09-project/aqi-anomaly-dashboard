from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd

from src.consumer_brief import (
    aqi_guidance,
    build_consumer_summary,
    export_csv_bytes,
    format_observation_status,
)
from src.app_helpers import (
    aqi_category,
    compute_kpis,
    data_quality_summary,
    filter_by_site_and_date,
    get_station_coordinates,
    infer_data_source,
    load_dashboard_data,
    load_metrics,
)
from src.risk_brief import build_station_risk_brief, describe_anomaly_evidence, select_risk_brief_columns
from src.station_comparison import (
    build_station_comparison,
    choose_recommended_station,
    export_comparison_csv,
)
from src.theme import (
    DEFAULT_THEME_NAME,
    THEME,
    THEME_OPTIONS,
    chart_color_sequence,
    get_theme,
    hex_to_rgb,
    validate_theme_contrast,
)
from src.utils import load_config, resolve_path


try:
    import plotly.express as px  # type: ignore
except Exception:  # pragma: no cover
    px = None

try:
    import plotly.graph_objects as go  # type: ignore
except Exception:  # pragma: no cover
    go = None

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None


DISPLAY_COLUMN_MAP = {
    "datetime": "時間",
    "site_name": "原始測站",
    "site_name_display": "測站",
    "county": "原始縣市",
    "county_display": "縣市",
    "aqi": "AQI",
    "pm25": "PM2.5",
    "pm10": "PM10",
    "o3": "臭氧 O3",
    "co": "一氧化碳 CO",
    "wind_speed": "風速",
    "wind_directions": "風向",
    "target_next_hour_aqi": "下一小時 AQI",
    "target_aqi": "目標 AQI",
    "actual_next_hour_aqi": "實際下一小時 AQI",
    "predicted_next_hour_aqi": "預測下一小時 AQI",
    "pred_moving_average": "Moving Average 預測",
    "pred_linear_regression": "Linear Regression 預測",
    "pred_random_forest": "Random Forest 預測",
    "prediction_error": "預測誤差",
    "lower_80_aqi": "80% 區間下界",
    "upper_80_aqi": "80% 區間上界",
    "lower_95_aqi": "95% 區間下界",
    "upper_95_aqi": "95% 區間上界",
    "threshold_watch_level": "關注層級",
    "threshold_watch_reason": "判讀依據",
    "absolute_error": "絕對誤差",
    "is_anomaly": "是否異常",
    "anomaly_score": "異常分數",
    "event_id": "事件編號",
    "end_datetime": "結束時間",
    "peak_datetime": "峰值時間",
    "event_points": "異常觀測筆數",
    "duration_hours": "持續小時",
    "peak_aqi": "峰值 AQI",
    "peak_pm25": "峰值 PM2.5",
    "max_anomaly_score": "最大異常分數",
    "evidence_summary": "判讀依據",
    "attention_level": "關注程度",
    "priority_score": "排序分數",
    "aqi_vs_baseline": "相對本站基準",
    "recent_6h_change": "近 6 小時變化",
    "predicted_next_hour_aqi": "下一小時預測 AQI",
    "evidence_summary": "判讀證據",
    "pseudo_anomaly": "規則式標籤",
    "zscore_anomaly": "Z-score 異常",
    "isolation_forest_anomaly": "Isolation Forest 異常",
    "timestamp": "時間",
    "anomaly": "異常事件",
    "quality_flag": "資料品質標記",
    "hour": "小時",
    "day_of_week": "星期",
    "month": "月份",
    "is_weekend": "是否週末",
    "lag_1_aqi": "AQI 前 1 小時",
    "lag_3_aqi": "AQI 前 3 小時",
    "rolling_3h_aqi": "AQI 3 小時移動平均",
    "rolling_6h_aqi": "AQI 6 小時移動平均",
    "rolling_12h_aqi": "AQI 12 小時移動平均",
    "pm25_lag_1": "PM2.5 前 1 小時",
    "pm25_rolling_3h": "PM2.5 3 小時移動平均",
    "aqi_diff": "AQI 時差",
    "pm25_diff": "PM2.5 時差",
    "observed_at": "觀測時間",
    "data_lag_hours": "資料落後小時",
    "freshness_state": "資料狀態",
    "current_aqi": "目前 AQI",
    "aqi_category": "AQI 等級",
    "forecast_change": "預測變化",
    "anomaly_evidence": "異常證據",
    "data_source": "資料來源",
}

# Backward-compatible alias for older tests/imports.
DISPLAY_COLUMNS = DISPLAY_COLUMN_MAP

MODEL_DISPLAY_NAMES = {
    "moving_average": "Moving Average 基準模型",
    "linear_regression": "Linear Regression",
    "random_forest": "Random Forest",
    "zscore": "Z-score 基準模型",
    "isolation_forest": "Isolation Forest",
}

METRIC_DISPLAY_COLUMNS = {
    "mae": "MAE",
    "rmse": "RMSE",
    "r2": "R2",
    "precision": "Precision",
    "recall": "Recall",
    "f1": "F1",
    "anomaly_rate": "異常比例",
    "anomaly_count": "異常筆數",
}


def inject_global_css(theme: dict[str, str] | None = None) -> None:
    if st is None:
        return
    theme = theme or THEME
    st.markdown(
        f"""
        <style>
        html, body {{
            color-scheme: dark;
            background: var(--background);
        }}
        :root {{
            --primary: {theme["primary"]};
            --secondary: {theme["secondary"]};
            --background: {theme["background"]};
            --surface: {theme["surface"]};
            --card: {theme["card"]};
            --sidebar: {theme["sidebar"]};
            --text: {theme["text"]};
            --muted-text: {theme["muted_text"]};
            --border: {theme["border"]};
            --accent: {theme["accent"]};
            --danger: {theme["danger"]};
            --warning: {theme["warning"]};
            --success: {theme["success"]};
            --table-header: {theme["table_header"]};
            --chart-grid: {theme["chart_grid"]};
            --shadow: {theme["shadow"]};
            --accent-soft: {theme["accent_soft"]};
            --success-soft: {theme["success_soft"]};
        }}
        .stApp {{
            background-color: var(--background);
            color: var(--text);
            font-size: 1rem;
        }}
        .block-container {{
            max-width: 1560px;
            padding: 2rem 2.75rem 3.5rem;
        }}
        [data-testid="stAppViewContainer"] {{
            background: var(--background);
        }}
        [data-testid="stHeader"] {{
            background: transparent;
        }}
        [data-testid="stSidebar"] > div:first-child {{
            padding: 1.5rem 1.1rem 2rem;
        }}
        [data-testid="stVerticalBlock"] {{
            gap: 0.75rem;
        }}
        [data-testid="stHorizontalBlock"] {{
            gap: 1rem;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: var(--text) !important;
            font-weight: 700 !important;
            letter-spacing: 0;
            text-wrap: balance;
        }}
        h1 {{ font-size: 2.25rem !important; line-height: 1.12 !important; }}
        h2 {{ font-size: 1.45rem !important; line-height: 1.25 !important; }}
        h3 {{ font-size: 1.08rem !important; line-height: 1.35 !important; }}
        p, li, label {{ line-height: 1.55; }}
        [data-testid="stMarkdownContainer"] p {{ margin-bottom: 0.55rem; }}
        a {{
            color: var(--primary) !important;
        }}
        [data-testid="stMarkdownContainer"],
        [data-testid="stWidgetLabel"],
        [data-testid="stCaptionContainer"] {{ color: var(--text); }}
        [data-testid="stCaptionContainer"] p {{ color: var(--muted-text) !important; }}
        section[data-testid="stSidebar"] {{
            background-color: var(--sidebar);
            border-right: 1px solid var(--border);
        }}
        section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
            gap: 0.55rem;
        }}
        section[data-testid="stSidebar"] h2 {{
            font-size: 0.82rem !important;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: var(--muted-text) !important;
            margin-top: 1.15rem;
            margin-bottom: 0.15rem;
        }}
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span,
        section[data-testid="stSidebar"] div[data-testid="stMetricValue"],
        section[data-testid="stSidebar"] div[data-testid="stMetricLabel"] {{
            color: var(--text) !important;
        }}
        section[data-testid="stSidebar"] [data-baseweb="select"] > div,
        section[data-testid="stSidebar"] [data-baseweb="input"] > div {{
            background-color: var(--surface) !important;
            border-color: var(--border) !important;
            color: var(--text) !important;
            min-height: 44px;
            border-radius: 8px !important;
        }}
        section[data-testid="stSidebar"] input {{
            color: var(--text) !important;
        }}
        [data-baseweb="select"] > div,
        [data-baseweb="base-input"] > div,
        [data-baseweb="input"] > div {{
            background-color: var(--surface) !important;
            border-color: var(--border) !important;
            color: var(--text) !important;
            min-height: 44px;
            border-radius: 8px !important;
        }}
        [role="listbox"], [role="option"] {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
        }}
        [role="option"]:hover, [aria-selected="true"][role="option"] {{
            background-color: var(--card) !important;
        }}
        button[data-baseweb="tab"] {{ color: var(--muted-text) !important; }}
        button[data-baseweb="tab"][aria-selected="true"] {{
            color: var(--text) !important;
            border-bottom-color: var(--accent) !important;
        }}
        [data-testid="stTabs"] [data-baseweb="tab-list"] {{
            display: flex;
            gap: 0.25rem;
            padding: 0.35rem;
            margin: 0.8rem 0 1.25rem;
            overflow-x: auto;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            scrollbar-width: none;
        }}
        [data-testid="stTabs"] [data-baseweb="tab-list"]::-webkit-scrollbar {{ display: none; }}
        [data-testid="stTabs"] button[data-baseweb="tab"] {{
            min-height: 44px;
            padding: 0.5rem 0.85rem;
            border: 1px solid transparent;
            border-radius: 6px;
            white-space: nowrap;
            touch-action: manipulation;
            transition: background-color 180ms ease, color 180ms ease, border-color 180ms ease;
        }}
        [data-testid="stTabs"] button[data-baseweb="tab"]:hover {{
            background: var(--card);
            color: var(--text) !important;
        }}
        [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {{
            background: var(--card);
            border-color: var(--border);
            box-shadow: inset 0 -2px 0 var(--accent);
        }}
        section[data-testid="stSidebar"] small,
        section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {{
            color: var(--muted-text) !important;
        }}
        .hero-band {{
            background: transparent;
            color: var(--text);
            padding: 0.7rem 0 1rem;
            border: 0;
            border-bottom: 1px solid var(--border);
            border-radius: 0;
            margin-bottom: 1.3rem;
            box-shadow: none;
        }}
        .hero-kicker, .hero-meta {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.55rem;
        }}
        .hero-kicker {{
            color: var(--muted-text);
            font-size: 0.75rem;
            font-weight: 800;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }}
        .sidebar-brand {{
            display: flex;
            align-items: center;
            gap: 0.65rem;
            padding: 0.2rem 0 1rem;
            border-bottom: 1px solid var(--border);
        }}
        .sidebar-brand-mark {{
            display: grid;
            place-items: center;
            width: 2.25rem;
            height: 2.25rem;
            border-radius: 7px;
            background: var(--accent);
            color: var(--background);
            font-size: 0.78rem;
            font-weight: 900;
            letter-spacing: 0.02em;
        }}
        .sidebar-brand strong {{
            display: block;
            color: var(--text);
            font-size: 0.88rem;
        }}
        .sidebar-brand span {{
            display: block;
            margin-top: 0.1rem;
            color: var(--muted-text);
            font-size: 0.75rem;
        }}
        .hero-band h1 {{
            color: var(--text) !important;
            margin: 0.45rem 0 0.35rem;
            font-size: 1.9rem !important;
            line-height: 1.2 !important;
        }}
        .hero-band p {{
            max-width: 72ch;
            margin: 0.25rem 0;
            color: var(--muted-text) !important;
        }}
        .hero-meta {{
            margin-top: 0.8rem;
            padding-top: 0.7rem;
            border-top: 1px solid var(--border);
            color: var(--muted-text);
            font-size: 0.82rem;
            gap: 0;
        }}
        .hero-meta-item {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.15rem 0.85rem;
            background: transparent;
            border: 0;
            border-left: 1px solid var(--border);
            border-radius: 0;
        }}
        .hero-meta-item:first-child {{ padding-left: 0; border-left: 0; }}
        .hero-meta-item strong {{ color: var(--text); }}
        .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.3rem 0.5rem;
            border-radius: 4px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-left: 3px solid var(--success);
            color: var(--text);
            font-size: 0.78rem;
            letter-spacing: 0;
        }}
        .status-dot {{
            width: 7px;
            height: 7px;
            flex: 0 0 7px;
            border-radius: 50%;
            background: var(--success);
            box-shadow: none;
        }}
        .metric-card,
        .kpi-card {{
            background: var(--card);
            color: var(--text);
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 6px;
            padding: 1rem 1.05rem;
            min-height: 112px;
            height: calc(100% - 14px);
            box-shadow: none;
            margin-bottom: 14px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .metric-card .label {{
            color: var(--muted-text) !important;
            font-size: 0.82rem;
            margin-bottom: 0.55rem;
            font-weight: 700;
        }}
        .metric-card .value {{
            color: var(--text) !important;
            font-size: 1.65rem;
            line-height: 1.15;
            font-weight: 800;
            overflow-wrap: anywhere;
            font-variant-numeric: tabular-nums;
        }}
        .metric-card .note {{
            color: var(--muted-text) !important;
            font-size: 0.75rem;
            margin-top: 0.55rem;
            overflow-wrap: anywhere;
        }}
        .section-note,
        .section-card {{
            color: var(--text);
            background: var(--surface);
            border: 1px solid var(--border);
            border-left: 3px solid var(--secondary);
            border-radius: 8px;
            padding: 0.8rem 0.95rem;
            margin: 0 0 1.25rem;
            font-weight: 500;
            font-size: 0.88rem;
            line-height: 1.65;
        }}
        .risk-brief {{
            background: var(--surface);
            color: var(--text);
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            padding: 1.05rem 1.1rem;
            margin: 0.15rem 0 1rem;
        }}
        .risk-brief-header {{
            display: flex;
            align-items: start;
            justify-content: space-between;
            gap: 1rem;
        }}
        .risk-brief-kicker {{
            color: var(--accent);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}
        .risk-brief h3 {{
            margin: 0.2rem 0 0;
            color: var(--text) !important;
            font-size: 1.22rem !important;
        }}
        .risk-brief p {{
            margin: 0.55rem 0 0;
            color: var(--text) !important;
            line-height: 1.6;
        }}
        .priority-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 32px;
            padding: 0.25rem 0.55rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--text);
            font-size: 0.8rem;
            font-weight: 800;
            white-space: nowrap;
        }}
        .priority-badge.critical {{
            background: var(--accent-soft);
            border-color: var(--accent);
        }}
        .priority-badge.watch {{
            background: var(--success-soft);
            border-color: var(--secondary);
        }}
        .priority-badge.normal {{
            background: var(--card);
            border-color: var(--border);
        }}
        .risk-facts {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.6rem;
            margin-top: 0.9rem;
            padding-top: 0.85rem;
            border-top: 1px solid var(--border);
        }}
        .risk-fact {{
            min-width: 0;
            padding-right: 0.6rem;
            border-right: 1px solid var(--border);
        }}
        .risk-fact:last-child {{ border-right: 0; }}
        .risk-fact-label {{
            display: block;
            color: var(--muted-text);
            font-size: 0.74rem;
            font-weight: 700;
        }}
        .risk-fact-value {{
            display: block;
            margin-top: 0.2rem;
            color: var(--text);
            font-size: 1.08rem;
            font-weight: 800;
            font-variant-numeric: tabular-nums;
            overflow-wrap: anywhere;
        }}
        .risk-disclaimer {{
            color: var(--muted-text) !important;
            font-size: 0.78rem;
        }}
        .section-header {{
            display: flex;
            align-items: end;
            justify-content: space-between;
            gap: 1rem;
            margin: 0.25rem 0 0.15rem;
        }}
        .section-header h2 {{ margin: 0.15rem 0 0; }}
        .section-kicker {{
            color: var(--accent);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }}
        .section-context {{
            color: var(--muted-text);
            font-size: 0.78rem;
            text-align: right;
        }}
        .metric-row-spacer {{
            height: 4px;
        }}
        .help-text {{
            color: var(--muted-text) !important;
            font-size: 0.95rem;
            line-height: 1.65;
        }}
        .warning-text {{
            color: var(--warning) !important;
            font-weight: 800;
        }}
        .danger-text {{
            color: var(--danger) !important;
            font-weight: 800;
        }}
        .success-text {{
            color: var(--success) !important;
            font-weight: 800;
        }}
        div[data-testid="stInfo"] {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border-left: 4px solid var(--secondary);
        }}
        div[data-testid="stWarning"] {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border-left: 4px solid var(--warning);
        }}
        .stAlert {{
            background-color: var(--surface) !important;
            color: var(--text) !important;
            border: 1px solid var(--border) !important;
            border-radius: 8px !important;
        }}
        div[data-testid="stMetricValue"] {{
            color: var(--text) !important;
            font-weight: 800 !important;
        }}
        div[data-testid="stMetricLabel"] {{
            color: var(--muted-text) !important;
            font-weight: 700 !important;
        }}
        div[data-testid="stMetricDelta"] {{
            color: var(--accent) !important;
        }}
        [data-testid="stPlotlyChart"] {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.25rem;
            overflow: hidden;
        }}
        .watch-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.55rem 0 1rem;
        }}
        .watch-card {{
            min-width: 0;
            padding: 0.9rem 0.95rem;
            border: 1px solid var(--border);
            border-top: 2px solid var(--warning);
            border-radius: 8px;
            background: var(--card);
        }}
        .watch-card.critical {{ border-top-color: var(--danger); }}
        .watch-card-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.65rem;
            color: var(--text);
            font-size: 0.9rem;
            font-weight: 800;
        }}
        .watch-level {{
            flex: 0 0 auto;
            padding: 0.2rem 0.42rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--accent);
            background: var(--surface);
            font-size: 0.74rem;
        }}
        .watch-card-main {{ display: flex; align-items: baseline; gap: 0.55rem; margin-top: 0.75rem; }}
        .watch-card-main strong {{ color: var(--text); font-size: 1.65rem; line-height: 1; }}
        .watch-card-main span, .watch-card p, .watch-bounds {{ color: var(--muted-text); }}
        .watch-card-main span {{ font-size: 0.76rem; }}
        .watch-card p {{ margin: 0.65rem 0; font-size: 0.82rem; line-height: 1.5; }}
        .watch-bounds {{ display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; font-size: 0.76rem; }}
        .watch-bounds strong {{ color: var(--text); font-variant-numeric: tabular-nums; }}        .map-selection-note {{
            margin: 0.4rem 0 0.9rem;
            color: var(--muted-text) !important;
            font-size: 0.82rem;
            line-height: 1.55;
        }}
        button {{
            border-radius: 8px !important;
            touch-action: manipulation;
            transition: background-color 180ms ease, border-color 180ms ease, color 180ms ease;
        }}
        button:focus-visible,
        [role="button"]:focus-visible,
        a:focus-visible,
        input:focus-visible,
        [data-baseweb="select"]:focus-within,
        [data-baseweb="base-input"]:focus-within {{
            outline: 3px solid var(--accent) !important;
            outline-offset: 2px !important;
        }}
        button:disabled,
        input:disabled,
        [aria-disabled="true"] {{
            cursor: not-allowed !important;
            opacity: 0.55;
        }}
        .table-shell {{
            overflow-x: auto;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--card);
            margin: 8px 0 18px;
            scrollbar-color: var(--border) var(--surface);
        }}
        .table-shell:focus-visible {{
            outline: 3px solid var(--accent);
            outline-offset: 2px;
        }}
        .dashboard-table {{
            width: 100%;
            border-collapse: collapse;
            color: var(--text);
            font-size: 0.84rem;
            font-variant-numeric: tabular-nums;
        }}
        .dashboard-table th {{
            background: var(--table-header);
            color: var(--text);
            text-align: left;
            padding: 0.72rem 0.78rem;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
            font-weight: 800;
        }}
        .dashboard-table td {{
            background: var(--card);
            color: var(--text);
            padding: 0.68rem 0.78rem;
            border-bottom: 1px solid var(--border);
            white-space: normal;
            overflow-wrap: anywhere;
        }}
        .dashboard-table tr:last-child td {{ border-bottom: 0; }}
        .dashboard-table tbody tr td {{
            transition: background-color 160ms ease;
        }}
        .dashboard-table tbody tr:hover td {{ background: var(--surface); }}
        .anomaly-case-table th:nth-child(1), .anomaly-case-table td:nth-child(1) {{ min-width: 4.8rem; }}
        .anomaly-case-table th:nth-child(2), .anomaly-case-table td:nth-child(2) {{
            min-width: 2.8rem;
            white-space: nowrap;
        }}
        .confidence-watch-table th:nth-child(6), .confidence-watch-table td:nth-child(6) {{
            min-width: 6.5rem;
            white-space: nowrap;
            font-weight: 800;
            color: var(--accent);
        }}
        .anomaly-case-table th:nth-child(3), .anomaly-case-table td:nth-child(3),
        .anomaly-case-table th:nth-child(4), .anomaly-case-table td:nth-child(4) {{
            min-width: 3.4rem;
            white-space: nowrap;
        }}
        .sidebar-summary {{ margin: 0; }}
        .sidebar-summary div {{
            display: flex;
            justify-content: space-between;
            gap: 12px;
            padding: 7px 0;
            border-bottom: 1px solid var(--border);
        }}
        .sidebar-summary dt {{ color: var(--muted-text); }}
        .sidebar-summary dd {{ color: var(--text); margin: 0; font-weight: 700; text-align: right; }}
        .dashboard-footer {{
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-top: 2.5rem;
            padding-top: 0.9rem;
            border-top: 1px solid var(--border);
            color: var(--muted-text);
            font-size: 0.75rem;
        }}
        .stApp, .stApp button, .stApp input, .stApp textarea, .stApp select {{
            font-family: "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif;
        }}
        .block-container {{
            max-width: 1480px;
            padding-top: 1.6rem;
        }}
        [data-testid="stVerticalBlock"] {{ gap: 1rem; }}
        .hero-band {{
            display: grid;
            grid-template-columns: minmax(0, 1fr);
            align-items: start;
            row-gap: 0.75rem;
            padding: 1rem 0 1.25rem;
            margin-bottom: 1.6rem;
        }}
        .hero-band h1 {{
            font-size: 2.15rem !important;
            letter-spacing: 0 !important;
        }}
        .hero-copy {{ min-width: 0; }}
        .hero-band p {{ max-width: 64ch; }}
        .hero-meta {{
            align-self: start;
            margin: 0;
            padding: 0;
            border-top: 0;
            justify-content: start;
            flex-wrap: wrap;
        }}
        .hero-meta-item {{
            min-height: 2.15rem;
            padding: 0.25rem 0.75rem;
        }}
        .dashboard-intro {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin: 0 0 1.15rem;
            padding: 0.7rem 0.85rem;
            color: var(--muted-text);
            border-top: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
            font-size: 0.86rem;
            line-height: 1.55;
        }}
        .dashboard-intro strong {{ color: var(--text); }}
        .signal-deck {{
            display: grid;
            grid-template-columns: minmax(230px, 1.25fr) repeat(3, minmax(150px, 1fr));
            gap: 0.75rem;
            margin: 0.45rem 0 1.85rem;
        }}
        .signal-primary, .signal-card {{
            min-width: 0;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--card);
        }}
        .signal-primary {{
            grid-row: span 2;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            padding: 1.15rem 1.2rem 1.05rem;
            border-left: 4px solid var(--accent);
        }}
        .signal-label {{
            color: var(--muted-text);
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.05em;
        }}
        .signal-value {{
            display: block;
            margin-top: 0.55rem;
            color: var(--text);
            font-size: 2.8rem;
            font-weight: 800;
            line-height: 1;
            font-variant-numeric: tabular-nums;
        }}
        .signal-context {{
            margin-top: 0.55rem;
            color: var(--muted-text);
            font-size: 0.84rem;
            line-height: 1.45;
        }}
        .signal-level {{
            display: inline-flex;
            width: fit-content;
            margin-top: 1.05rem;
            padding: 0.28rem 0.5rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            background: var(--surface);
            color: var(--text);
            font-size: 0.82rem;
            font-weight: 800;
        }}
        .signal-card {{
            display: flex;
            min-height: 106px;
            flex-direction: column;
            justify-content: space-between;
            padding: 0.9rem 0.95rem;
            transition: border-color 180ms ease, background-color 180ms ease;
        }}
        .signal-card:hover {{
            background: var(--surface);
            border-color: var(--secondary);
        }}
        .signal-card .signal-value {{
            margin: 0.35rem 0 0;
            font-size: 1.5rem;
            line-height: 1.15;
        }}
        .signal-card .signal-context {{
            margin-top: 0.4rem;
            font-size: 0.75rem;
        }}
        .signal-card.accent {{ border-top: 2px solid var(--accent); }}
        .signal-card.alert {{ border-top: 2px solid var(--danger); }}
        .signal-card.calm {{ border-top: 2px solid var(--secondary); }}
        .guidance-panel {{
            margin: 0 0 1.85rem;
            padding: 1.05rem 1.15rem;
            border: 1px solid var(--border);
            border-left: 4px solid var(--secondary);
            border-radius: 8px;
            background: var(--surface);
            color: var(--text);
        }}
        .guidance-heading {{
            display: flex;
            align-items: start;
            justify-content: space-between;
            gap: 1rem;
        }}
        .guidance-kicker {{
            color: var(--accent);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.06em;
        }}
        .guidance-heading h2 {{
            margin: 0.22rem 0 0;
            color: var(--text) !important;
            font-size: 1.2rem !important;
        }}
        .guidance-time {{
            display: grid;
            gap: 0.15rem;
            color: var(--muted-text);
            font-size: 0.74rem;
            text-align: right;
        }}
        .guidance-time strong {{ color: var(--text); font-size: 0.86rem; }}
        .guidance-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin-top: 0.9rem;
        }}
        .guidance-grid > div {{
            min-width: 0;
            padding: 0.8rem 0.85rem;
            border: 1px solid var(--border);
            border-radius: 6px;
            background: var(--card);
        }}
        .guidance-grid span {{ color: var(--accent); font-size: 0.76rem; font-weight: 800; }}
        .guidance-grid p {{ margin: 0.3rem 0 0; color: var(--text) !important; line-height: 1.55; }}
        .guidance-disclaimer {{
            margin: 0.75rem 0 0;
            color: var(--muted-text) !important;
            font-size: 0.76rem;
            line-height: 1.5;
        }}
        .guidance-disclaimer a {{ color: var(--accent) !important; font-weight: 800; }}
        .comparison-recommendation {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin: 0.25rem 0 1rem;
            padding: 0.95rem 1rem;
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            background: var(--surface);
            color: var(--text);
        }}
        .comparison-recommendation span {{ color: var(--muted-text); font-size: 0.78rem; font-weight: 700; }}
        .comparison-recommendation strong {{ display: block; margin-top: 0.18rem; color: var(--text); font-size: 1.12rem; }}
        .comparison-recommendation-value {{ color: var(--accent); font-size: 1rem; font-weight: 800; white-space: nowrap; }}
        .comparison-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.75rem 0 1.2rem;
        }}
        .comparison-card {{
            min-width: 0;
            padding: 0.95rem 1rem;
            border: 1px solid var(--border);
            border-top: 3px solid var(--secondary);
            border-radius: 8px;
            background: var(--card);
            color: var(--text);
        }}
        .comparison-card.stale {{ border-top-color: var(--warning); }}
        .comparison-card.anomaly {{ border-top-color: var(--danger); }}
        .comparison-card-head {{ display: flex; align-items: start; justify-content: space-between; gap: 0.6rem; }}
        .comparison-card-head strong {{ color: var(--text); font-size: 1rem; overflow-wrap: anywhere; }}
        .comparison-card-head span {{ color: var(--muted-text); font-size: 0.74rem; }}
        .comparison-state {{
            flex: 0 0 auto;
            padding: 0.2rem 0.4rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            background: var(--surface);
            color: var(--text) !important;
            font-weight: 800;
        }}
        .comparison-aqi {{ display: flex; align-items: end; gap: 0.55rem; margin-top: 0.85rem; }}
        .comparison-aqi strong {{ color: var(--text); font-size: 2rem; line-height: 1; font-variant-numeric: tabular-nums; }}
        .comparison-aqi span {{ color: var(--accent); font-size: 0.78rem; font-weight: 800; }}
        .comparison-facts {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.55rem; margin-top: 0.85rem; }}
        .comparison-fact {{ padding-top: 0.55rem; border-top: 1px solid var(--border); min-width: 0; }}
        .comparison-fact span {{ display: block; color: var(--muted-text); font-size: 0.7rem; }}
        .comparison-fact strong {{ display: block; margin-top: 0.16rem; color: var(--text); font-size: 0.88rem; overflow-wrap: anywhere; }}
        .comparison-time {{ margin: 0.75rem 0 0; color: var(--muted-text) !important; font-size: 0.72rem; }}
        .priority-queue {{
            display: grid;
            gap: 0.55rem;
            margin-top: 0.55rem;
        }}
        .priority-row {{
            display: grid;
            grid-template-columns: 1.85rem minmax(0, 1fr) auto;
            align-items: start;
            gap: 0.65rem;
            padding: 0.76rem 0;
            border-bottom: 1px solid var(--border);
        }}
        .priority-row:first-child {{ padding-top: 0.25rem; }}
        .priority-row:last-child {{ border-bottom: 0; }}
        .priority-rank {{
            display: grid;
            place-items: center;
            width: 1.85rem;
            height: 1.85rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--accent);
            background: var(--surface);
            font-size: 0.78rem;
            font-weight: 800;
            font-variant-numeric: tabular-nums;
        }}
        .priority-place {{
            min-width: 0;
            color: var(--text);
            font-size: 0.95rem;
            font-weight: 800;
            line-height: 1.35;
        }}
        .priority-evidence {{
            display: block;
            margin-top: 0.22rem;
            color: var(--muted-text);
            font-size: 0.77rem;
            line-height: 1.45;
        }}
        .priority-aqi {{
            color: var(--text);
            font-size: 1rem;
            font-weight: 800;
            font-variant-numeric: tabular-nums;
            text-align: right;
            white-space: nowrap;
        }}
        .priority-aqi span {{
            display: block;
            margin-top: 0.12rem;
            color: var(--muted-text);
            font-size: 0.68rem;
            font-weight: 700;
        }}
        .queue-empty {{
            margin: 0.75rem 0 0;
            color: var(--muted-text);
            font-size: 0.88rem;
        }}
        .watch-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.55rem 0 1rem;
        }}
        .watch-card {{
            min-width: 0;
            padding: 0.9rem 0.95rem;
            border: 1px solid var(--border);
            border-top: 2px solid var(--warning);
            border-radius: 8px;
            background: var(--card);
        }}
        .watch-card.critical {{ border-top-color: var(--danger); }}
        .watch-card-head {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.65rem;
            color: var(--text);
            font-size: 0.9rem;
            font-weight: 800;
        }}
        .watch-level {{
            flex: 0 0 auto;
            padding: 0.2rem 0.42rem;
            border: 1px solid var(--border);
            border-radius: 4px;
            color: var(--accent);
            background: var(--surface);
            font-size: 0.74rem;
        }}
        .watch-card-main {{ display: flex; align-items: baseline; gap: 0.55rem; margin-top: 0.75rem; }}
        .watch-card-main strong {{ color: var(--text); font-size: 1.65rem; line-height: 1; }}
        .watch-card-main span, .watch-card p, .watch-bounds {{ color: var(--muted-text); }}
        .watch-card-main span {{ font-size: 0.76rem; }}
        .watch-card p {{ margin: 0.65rem 0; font-size: 0.82rem; line-height: 1.5; }}
        .watch-bounds {{ display: flex; flex-wrap: wrap; gap: 0.5rem 1rem; font-size: 0.76rem; }}
        .watch-bounds strong {{ color: var(--text); font-variant-numeric: tabular-nums; }}        .map-selection-note {{
            display: flex;
            align-items: center;
            min-height: 2rem;
            margin: 0.2rem 0 0;
            padding: 0.25rem 0;
            border-top: 1px solid var(--border);
        }}
        .section-divider {{
            height: 1px;
            margin: 1.8rem 0;
            background: var(--border);
        }}
        [data-testid="stPlotlyChart"] {{
            border-radius: 8px;
            padding: 0.45rem;
        }}
        .table-shell {{
            margin: 0.5rem 0 1.15rem;
            border-radius: 6px;
        }}
        .dashboard-table th {{
            position: sticky;
            top: 0;
            z-index: 1;
            padding: 0.68rem 0.72rem;
            font-size: 0.78rem;
        }}
        .dashboard-table td {{
            padding: 0.7rem 0.72rem;
            vertical-align: top;
        }}
        @media (max-width: 900px) {{
            .block-container {{ padding: 1.5rem 1.35rem 3rem; }}
            h1 {{ font-size: 2rem !important; }}
            .section-header {{ align-items: start; flex-direction: column; gap: 0.25rem; }}
            .section-context {{ text-align: left; }}
            .hero-band {{ grid-template-columns: 1fr; gap: 0.9rem; }}
            .hero-meta {{ justify-content: start; }}
            .signal-deck {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .comparison-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .signal-primary {{ grid-row: auto; grid-column: span 2; }}
        }}
        @media (max-width: 640px) {{
            .block-container {{ padding: 3.75rem 0.9rem 2.5rem; }}
            h1 {{ font-size: 1.75rem !important; }}
            h2 {{ font-size: 1.25rem !important; }}
            .hero-band {{ padding: 0.55rem 0 0.9rem; margin-bottom: 1rem; }}
            .hero-band h1 {{ font-size: 1.65rem !important; }}
            .hero-band p {{ font-size: 1rem; }}
            .hero-kicker, .status-pill {{ font-size: 0.84rem; }}
            .hero-meta {{ align-items: stretch; flex-direction: column; }}
            .hero-meta-item, .status-pill {{
                width: 100%;
                box-sizing: border-box;
                font-size: 0.9rem;
            }}
            .hero-meta-item {{ border-left: 0; padding-left: 0; }}
            .hero-kicker .status-pill {{ width: fit-content; }}
            .metric-card {{ min-height: 98px; padding: 0.9rem; }}
            .metric-card .value {{ font-size: 1.5rem; }}
            .metric-card .label {{ font-size: 0.9rem; }}
            .metric-card .note {{ font-size: 0.82rem; }}
            .section-note, .section-card {{ font-size: 0.95rem; }}
            .risk-brief {{ padding: 0.95rem; }}
            .risk-brief-header {{ flex-direction: column; gap: 0.55rem; }}
            .risk-facts {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem 0.55rem; }}
            .risk-fact:nth-child(2) {{ border-right: 0; }}
            .risk-fact:nth-child(-n+2) {{ padding-bottom: 0.7rem; border-bottom: 1px solid var(--border); }}
            section[data-testid="stSidebar"] [data-baseweb="select"],
            section[data-testid="stSidebar"] input {{
                font-size: 1rem !important;
            }}
            .table-shell {{ margin-left: -0.1rem; margin-right: -0.1rem; }}
            .dashboard-table {{ font-size: 0.84rem; }}
            .dashboard-table th, .dashboard-table td {{ padding: 0.58rem 0.55rem; }}
            .dashboard-footer {{ align-items: start; flex-direction: column; gap: 0.25rem; }}
            .dashboard-intro {{ align-items: start; flex-direction: column; gap: 0.25rem; }}
            [data-testid="stTabs"] [data-baseweb="tab-list"] {{
                flex-wrap: wrap;
                gap: 0.2rem;
                overflow-x: visible;
                padding: 0.25rem;
            }}
            [data-testid="stTabs"] button[data-baseweb="tab"] {{
                flex: 1 1 calc(33.333% - 0.2rem);
                min-width: 0;
                min-height: 44px;
                padding: 0.4rem 0.3rem;
                font-size: 0.75rem;
                justify-content: center;
            }}
            .signal-deck {{ grid-template-columns: 1fr; gap: 0.65rem; }}
            .signal-primary {{ grid-column: auto; padding: 1rem; }}
            .signal-value {{ font-size: 2.45rem; }}
            .signal-card {{ min-height: 94px; }}
            .guidance-heading {{ display: grid; }}
            .guidance-time {{ text-align: left; }}
            .guidance-grid {{ grid-template-columns: 1fr; }}
            .comparison-recommendation {{ align-items: start; flex-direction: column; }}
            .comparison-grid {{ grid-template-columns: 1fr; }}
            .priority-row {{ grid-template-columns: 1.75rem minmax(0, 1fr) auto; gap: 0.5rem; }}
            .priority-rank {{ width: 1.75rem; height: 1.75rem; }}
            .watch-grid {{ grid-template-columns: 1fr; }}
            .watch-card {{ padding: 0.85rem; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
            *, *::before, *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                scroll-behavior: auto !important;
                transition-duration: 0.01ms !important;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_theme(theme: dict[str, str] | None = None) -> None:
    inject_global_css(theme)


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:,.1f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _format_optional_number(value: object, signed: bool = False) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "資料不足"
    return f"{float(numeric):+,.1f}" if signed else f"{float(numeric):,.1f}"


def metric_card(label: str, value: object, note: str = "") -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="label">{escape(label)}</div>
            <div class="value">{escape(_format_value(value))}</div>
            <div class="note">{escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def signal_deck(
    latest_aqi: object,
    category: object,
    latest_note: str,
    metric_items: list[tuple[str, object, str, str]],
) -> None:
    """Render a compact, signal-first overview without nested Streamlit cards."""
    cards = "".join(
        f"""
        <article class="signal-card {escape(tone)}">
            <span class="signal-label">{escape(label)}</span>
            <strong class="signal-value">{escape(_format_value(value))}</strong>
            <span class="signal-context">{escape(note)}</span>
        </article>
        """
        for label, value, note, tone in metric_items
    )
    st.markdown(
        f"""
        <section class="signal-deck" aria-label="核心空氣品質指標">
            <article class="signal-primary">
                <div>
                    <span class="signal-label">最新 AQI</span>
                    <strong class="signal-value">{escape(_format_value(latest_aqi))}</strong>
                    <span class="signal-context">{escape(latest_note)}</span>
                </div>
                <span class="signal-level">AQI 等級：{escape(str(category))}</span>
            </article>
            {cards}
        </section>
        """,
        unsafe_allow_html=True,
    )


def activity_guidance_panel(latest_aqi: object, data_source: str, observed_at: object) -> None:
    guidance = aqi_guidance(latest_aqi if observed_at is not None and not pd.isna(observed_at) else None)
    status = format_observation_status(observed_at, data_source)
    source_note = (
        "Sample Data 僅供模擬，不是官方即時資訊。"
        if data_source != "API Data"
        else "資料時效取決於上游 API，重要決策請查閱官方資訊。"
    )
    st.markdown(
        f"""
        <section class="guidance-panel" aria-label="空氣品質活動建議">
            <div class="guidance-heading">
                <div>
                    <span class="guidance-kicker">空氣品質活動建議</span>
                    <h2>{escape(str(guidance['category']))}</h2>
                </div>
                <div class="guidance-time">
                    <span>{escape(status['label'])}</span>
                    <strong>{escape(status['value'])}</strong>
                </div>
            </div>
            <div class="guidance-grid">
                <div><span>一般民眾</span><p>{escape(str(guidance['general']))}</p></div>
                <div><span>敏感族群</span><p>{escape(str(guidance['sensitive']))}</p></div>
            </div>
            <p class="guidance-disclaimer">依環境部 AQI 分級整理。{escape(source_note)}
                <a href="https://airtw.moenv.gov.tw/CHT/Information/Standard/AirQualityIndicatorNew.aspx" target="_blank" rel="noopener noreferrer">查看環境部 AQI 說明</a>
            </p>
        </section>
        """,
        unsafe_allow_html=True,
    )

def section_header(kicker: str, title: str, context: str = "") -> None:
    context_html = f'<span class="section-context">{escape(context)}</span>' if context else ""
    st.markdown(
        f"""
        <div class="section-header">
            <div>
                <div class="section-kicker">{escape(kicker)}</div>
                <h2>{escape(title)}</h2>
            </div>
            {context_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_table(
    df: pd.DataFrame,
    empty_message: str = "目前沒有可顯示的資料。",
    label: str = "資料表",
    table_class: str = "",
) -> None:
    if df.empty:
        st.info(empty_message)
        return
    display = df.copy()
    for column in display.columns:
        if pd.api.types.is_datetime64_any_dtype(display[column]):
            display[column] = display[column].dt.strftime("%Y/%m/%d %H:%M")
        elif pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].round(3)
    table_classes = " ".join(part for part in ["dashboard-table", table_class] if part)
    table_html = display.to_html(index=False, border=0, classes=table_classes, escape=True)
    st.markdown(
        f'<div class="table-shell" role="region" aria-label="{escape(label)}" tabindex="0">{table_html}</div>',
        unsafe_allow_html=True,
    )


def _display_source(source: str) -> str:
    return "API Data" if source == "API Data" else "Sample Data"


def _source_caption(source: str) -> str:
    return "環境部 API 資料" if source == "API Data" else "Sample Data（模擬資料）"


def _rename_for_display(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={k: v for k, v in DISPLAY_COLUMN_MAP.items() if k in df.columns})


def _model_metrics_table(metrics: dict[str, Any]) -> pd.DataFrame:
    comparison = metrics.get("model_comparison", metrics)
    rows: list[dict[str, Any]] = []
    if isinstance(comparison, dict):
        for model_name, values in comparison.items():
            if isinstance(values, dict):
                rows.append({"模型": MODEL_DISPLAY_NAMES.get(model_name, model_name), **values})
    table = pd.DataFrame(rows)
    if table.empty:
        return table
    return table.rename(columns={k: v for k, v in METRIC_DISPLAY_COLUMNS.items() if k in table.columns})


def _backtest_aggregate_table(metrics: dict[str, Any]) -> pd.DataFrame:
    """Flatten rolling-origin aggregate metrics into dashboard-ready rows."""
    aggregate = metrics.get("aggregate", {})
    if not isinstance(aggregate, dict):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for model_name, values in aggregate.items():
        if isinstance(values, dict):
            rows.append({"模型": MODEL_DISPLAY_NAMES.get(model_name, model_name), **values})

    table = pd.DataFrame(rows)
    if table.empty:
        return table
    return table.rename(columns={key: value for key, value in METRIC_DISPLAY_COLUMNS.items() if key in table.columns})



def _confidence_summary_table(metrics: dict[str, Any]) -> pd.DataFrame:
    intervals = metrics.get("intervals", {})
    if not isinstance(intervals, dict):
        return pd.DataFrame()
    rows: list[dict[str, object]] = []
    for key in sorted(intervals, key=lambda value: int(value) if str(value).isdigit() else 999):
        values = intervals.get(key)
        if not isinstance(values, dict):
            continue
        coverage = values.get("empirical_coverage")
        rows.append(
            {
                "預測區間": f"{key}%",
                "校準誤差分位數": values.get("residual_quantile", "N/A"),
                "最終測試覆蓋率": "N/A" if coverage is None else f"{float(coverage) * 100:.1f}%",
                "平均區間寬度": values.get("mean_width", "N/A"),
            }
        )
    return pd.DataFrame(rows)


def _threshold_watch_table(predictions: pd.DataFrame) -> pd.DataFrame:
    columns = ["時間", "測站", "預測 AQI", "80% 上界", "95% 上界", "關注層級", "判讀依據"]
    required = {
        "datetime",
        "site_name_display",
        "predicted_next_hour_aqi",
        "upper_80_aqi",
        "upper_95_aqi",
        "threshold_watch_level",
        "threshold_watch_reason",
    }
    if predictions.empty or not required.issubset(predictions.columns):
        return pd.DataFrame(columns=columns)
    table = predictions[predictions["threshold_watch_level"] != "區間穩定"].copy()
    if table.empty:
        return pd.DataFrame(columns=columns)
    table["_severity"] = table["threshold_watch_level"].map({"跨級關注": 0, "不確定性關注": 1}).fillna(2)
    table = table.sort_values(["_severity", "upper_95_aqi", "datetime"], ascending=[True, False, False])
    table = table[
        [
            "datetime",
            "site_name_display",
            "predicted_next_hour_aqi",
            "upper_80_aqi",
            "upper_95_aqi",
            "threshold_watch_level",
            "threshold_watch_reason",
        ]
    ].rename(
        columns={
            "datetime": "時間",
            "site_name_display": "測站",
            "predicted_next_hour_aqi": "預測 AQI",
            "upper_80_aqi": "80% 上界",
            "upper_95_aqi": "95% 上界",
            "threshold_watch_level": "關注層級",
            "threshold_watch_reason": "判讀依據",
        }
    )
    return table.reset_index(drop=True)

def _threshold_watch_cards_html(table: pd.DataFrame, limit: int = 6) -> str:
    cards: list[str] = []
    for _, row in table.head(limit).iterrows():
        timestamp = pd.to_datetime(row.get("時間"), errors="coerce")
        time_label = "時間未知" if pd.isna(timestamp) else timestamp.strftime("%m/%d %H:%M")
        level = str(row.get("關注層級", "不確定性關注"))
        tone = "critical" if level == "跨級關注" else "uncertain"
        cards.append(
            f'<article class="watch-card {tone}">'
            f'<div class="watch-card-head"><span>{escape(str(row.get("測站", "未知測站")))}</span>'
            f'<span class="watch-level">{escape(level)}</span></div>'
            f'<div class="watch-card-main"><strong>{escape(_format_optional_number(row.get("預測 AQI")))}</strong>'
            f'<span>預測 AQI · {escape(time_label)}</span></div>'
            f'<p>{escape(str(row.get("判讀依據", "尚無判讀依據")))}</p>'
            f'<div class="watch-bounds"><span>80% 上界 <strong>{escape(_format_optional_number(row.get("80% 上界")))}</strong></span>'
            f'<span>95% 上界 <strong>{escape(_format_optional_number(row.get("95% 上界")))}</strong></span></div>'
            "</article>"
        )
    return f'<section class="watch-grid" aria-label="AQI 預測區間跨級關注">{"".join(cards)}</section>'


def comparison_cards_html(comparison: pd.DataFrame) -> str:
    cards: list[str] = []
    for _, row in comparison.iterrows():
        timestamp = pd.to_datetime(row.get("observed_at"), errors="coerce")
        time_label = "時間未知" if pd.isna(timestamp) else timestamp.strftime("%m/%d %H:%M")
        state = str(row.get("freshness_state", "資料狀態未知"))
        is_anomaly = bool(row.get("is_anomaly", False))
        tone = "anomaly" if is_anomaly else "stale" if state == "資料較舊" else "current"
        interval = (
            f"{_format_optional_number(row.get('lower_80_aqi'))}–{_format_optional_number(row.get('upper_80_aqi'))}"
            if pd.notna(row.get("lower_80_aqi")) and pd.notna(row.get("upper_80_aqi"))
            else "資料不足"
        )
        cards.append(
            f'<article class="comparison-card {tone}">'
            f'<div class="comparison-card-head"><div><strong>{escape(str(row.get("site_name_display", "未知測站")))}</strong>'
            f'<span>{escape(str(row.get("county_display", "未知地區")))}</span></div>'
            f'<span class="comparison-state">{escape(state)}</span></div>'
            f'<div class="comparison-aqi"><strong>{escape(_format_optional_number(row.get("current_aqi")))}</strong>'
            f'<span>{escape(str(row.get("aqi_category", "無資料")))}</span></div>'
            f'<div class="comparison-facts">'
            f'<div class="comparison-fact"><span>目前 AQI</span><strong>{escape(_format_optional_number(row.get("current_aqi")))}</strong></div>'
            f'<div class="comparison-fact"><span>下一小時</span><strong>{escape(_format_optional_number(row.get("predicted_next_hour_aqi")))}</strong></div>'
            f'<div class="comparison-fact"><span>80% 預測區間</span><strong>{escape(interval)}</strong></div>'
            f'<div class="comparison-fact"><span>本站同時段基準</span><strong>{escape(_format_optional_number(row.get("baseline_aqi")))}</strong></div>'
            f'<div class="comparison-fact"><span>相對本站基準</span><strong>{escape(_format_optional_number(row.get("aqi_vs_baseline"), signed=True))}</strong></div>'
            f'<div class="comparison-fact"><span>PM2.5</span><strong>{escape(_format_optional_number(row.get("pm25")))}</strong></div>'
            f'</div><p class="comparison-time">觀測時間 {escape(time_label)}</p></article>'
        )
    return f'<section class="comparison-grid" aria-label="測站比較卡片">{"".join(cards)}</section>'


def apply_plotly_theme(fig: Any, theme: dict[str, str], title: str | None = None):
    layout: dict[str, Any] = {
        "paper_bgcolor": theme["card"],
        "plot_bgcolor": theme["card"],
        "font": {"color": theme["text"]},
        "xaxis": {
            "gridcolor": theme["chart_grid"],
            "tickfont": {"color": theme["muted_text"]},
            "title": {"font": {"color": theme["text"]}},
        },
        "yaxis": {
            "gridcolor": theme["chart_grid"],
            "tickfont": {"color": theme["muted_text"]},
            "title": {"font": {"color": theme["text"]}},
        },
        "legend": {
            "font": {"color": theme["text"]},
            "bgcolor": theme["card"],
            "bordercolor": theme["border"],
        },
        "hoverlabel": {
            "bgcolor": theme["surface"],
            "font_color": theme["text"],
            "bordercolor": theme["border"],
        },
    }
    if title:
        layout["title"] = title
    fig.update_layout(**layout)
    return fig


def _safe_date_range(df: pd.DataFrame) -> tuple[Any, Any] | None:
    if df.empty or "datetime" not in df:
        return None
    dates = pd.to_datetime(df["datetime"], errors="coerce").dropna()
    if dates.empty:
        return None
    return dates.min().date(), dates.max().date()


def _select_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    existing = [column for column in columns if column in df.columns]
    return df[existing].copy() if existing else pd.DataFrame()


def _site_lookup(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["site_name", "site_name_display"])
    cols = [col for col in ["site_name", "site_name_display"] if col in df.columns]
    if not cols:
        return pd.DataFrame(columns=["site_name", "site_name_display"])
    lookup = df[cols].drop_duplicates().copy()
    if "site_name" not in lookup.columns:
        lookup["site_name"] = lookup["site_name_display"]
    if "site_name_display" not in lookup.columns:
        lookup["site_name_display"] = lookup["site_name"]
    return lookup.sort_values(["site_name_display", "site_name"]).reset_index(drop=True)


def _plot_chart(fig: Any) -> None:
    st.plotly_chart(
        fig,
        width="stretch",
        config={
            "displaylogo": False,
            "responsive": True,
            "scrollZoom": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {"format": "png", "scale": 2},
        },
    )


def _priority_badge_class(attention_level: object) -> str:
    return {
        "優先檢視": "critical",
        "持續觀察": "watch",
    }.get(str(attention_level), "normal")


def _render_risk_brief(brief: pd.DataFrame) -> None:
    if brief.empty:
        st.info("目前篩選條件沒有足夠資料建立測站脈絡判讀。")
        return

    top = brief.iloc[0]
    baseline_label = "資料不足"
    if pd.notna(top.get("baseline_aqi")):
        baseline_label = f"{_format_optional_number(top.get('baseline_aqi'))}（n={int(top.get('baseline_samples', 0))}）"
    prediction_label = _format_optional_number(top.get("predicted_next_hour_aqi"))
    delta_label = _format_optional_number(top.get("aqi_vs_baseline"), signed=True)
    trend_label = f"{escape(str(top.get('trend_label', '資料不足')))} {_format_optional_number(top.get('recent_6h_change'), signed=True)}"
    st.markdown(
        f"""
        <section class="risk-brief" aria-label="目前優先關注測站">
            <div class="risk-brief-header">
                <div>
                    <div class="risk-brief-kicker">測站脈絡決策摘要</div>
                    <h3>{escape(str(top.get('site_name_display', '未知測站')))}：{escape(str(top.get('attention_level', '一般監測')))}</h3>
                </div>
                <span class="priority-badge {_priority_badge_class(top.get('attention_level'))}">{escape(str(top.get('attention_level', '一般監測')))}</span>
            </div>
            <p>{escape(str(top.get('evidence_summary', '目前沒有可用的判讀證據。')))}</p>
            <div class="risk-facts">
                <div class="risk-fact"><span class="risk-fact-label">目前 AQI</span><span class="risk-fact-value">{_format_optional_number(top.get('latest_aqi'))}</span></div>
                <div class="risk-fact"><span class="risk-fact-label">同時段基準</span><span class="risk-fact-value">{escape(baseline_label)}</span></div>
                <div class="risk-fact"><span class="risk-fact-label">近 6 小時</span><span class="risk-fact-value">{trend_label}</span></div>
                <div class="risk-fact"><span class="risk-fact-label">下一小時預測</span><span class="risk-fact-value">{prediction_label}</span></div>
            </div>
            <p class="risk-disclaimer">排序只用於人工檢視優先順序，不是官方 AQI 警報、因果判定或健康風險估計。</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_priority_queue(brief: pd.DataFrame, limit: int = 4) -> None:
    if brief.empty:
        st.markdown('<p class="queue-empty">目前沒有足夠資料建立測站優先序。</p>', unsafe_allow_html=True)
        return
    rows: list[str] = []
    for rank, (_, row) in enumerate(brief.head(limit).iterrows(), start=1):
        latest_aqi = _format_optional_number(row.get("latest_aqi"))
        site_name = str(row.get("site_name_display", "未知測站"))
        evidence = str(row.get("evidence_summary", "尚無判讀依據"))
        attention = str(row.get("attention_level", "一般觀察"))
        rows.append(
            f'<article class="priority-row" aria-label="第 {rank} 優先檢視測站">'
            f'<span class="priority-rank">{rank}</span>'
            f'<div><div class="priority-place">{escape(site_name)}</div>'
            f'<span class="priority-evidence">{escape(evidence)}</span></div>'
            f'<div class="priority-aqi">{escape(latest_aqi)}<span>{escape(attention)}</span></div>'
            "</article>"
        )
    st.markdown(f'<section class="priority-queue">{"".join(rows)}</section>', unsafe_allow_html=True)


def _risk_brief_table(brief: pd.DataFrame) -> pd.DataFrame:
    display = select_risk_brief_columns(
        brief,
        [
            "site_name_display",
            "latest_aqi",
            "aqi_vs_baseline",
            "recent_6h_change",
            "predicted_next_hour_aqi",
            "anomaly_flag",
            "attention_level",
            "evidence_summary",
        ],
    ).copy()
    if display.empty:
        return display
    display = display.rename(
        columns={
            "site_name_display": "測站",
            "latest_aqi": "目前 AQI",
            "aqi_vs_baseline": "相對本站基準",
            "recent_6h_change": "近 6 小時變化",
            "predicted_next_hour_aqi": "下一小時預測",
            "anomaly_flag": "異常旗標",
            "attention_level": "關注程度",
            "evidence_summary": "判讀證據",
        }
    )
    for column in ["目前 AQI", "下一小時預測"]:
        if column in display:
            display[column] = display[column].map(_format_optional_number)
    for column in ["相對本站基準", "近 6 小時變化"]:
        if column in display:
            display[column] = display[column].map(lambda value: _format_optional_number(value, signed=True))
    if "異常旗標" in display:
        display["異常旗標"] = display["異常旗標"].map({1: "有", 0: "無"}).fillna("資料不足")
    return display


def _station_map_data(brief: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in brief.iterrows():
        coordinates = get_station_coordinates(row.get("site_name_display"), row.get("county_display"))
        if coordinates is None:
            continue
        latitude, longitude = coordinates
        rows.append(
            {
                "site_name_display": str(row.get("site_name_display", "未知測站")),
                "county_display": str(row.get("county_display", "未知地區")),
                "latitude": latitude,
                "longitude": longitude,
                "latest_aqi": row.get("latest_aqi"),
                "latest_pm25": row.get("latest_pm25"),
                "attention_level": str(row.get("attention_level", "一般監測")),
                "evidence_summary": str(row.get("evidence_summary", "")),
            }
        )
    return pd.DataFrame(rows)


def _build_station_map(brief: pd.DataFrame, theme: dict[str, str]):
    if go is None:
        return None
    map_data = _station_map_data(brief)
    if map_data.empty:
        return None
    color_map = {
        "優先檢視": theme["danger"],
        "持續觀察": theme["accent"],
        "一般監測": theme["secondary"],
    }
    marker_sizes = [max(15, min(34, 13 + float(aqi) / 7)) for aqi in map_data["latest_aqi"]]
    # This simplified outline provides an offline spatial frame, not county boundaries.
    taiwan_outline = [
        (121.95, 25.30), (121.72, 25.25), (121.47, 25.17), (121.21, 24.98),
        (120.98, 24.73), (120.76, 24.38), (120.54, 23.95), (120.31, 23.50),
        (120.17, 23.08), (120.31, 22.70), (120.61, 22.26), (120.84, 21.90),
        (121.04, 22.06), (121.12, 22.43), (121.24, 22.83), (121.41, 23.22),
        (121.54, 23.62), (121.64, 24.00), (121.73, 24.36), (121.84, 24.71),
        (122.01, 25.02), (121.95, 25.30),
    ]
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[longitude for longitude, _ in taiwan_outline],
            y=[latitude for _, latitude in taiwan_outline],
            mode="lines",
            fill="toself",
            fillcolor=theme["background"],
            line={"color": theme["border"], "width": 1.5},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=map_data["longitude"],
            y=map_data["latitude"],
            customdata=map_data[["site_name_display", "county_display", "latest_aqi", "latest_pm25", "attention_level"]],
            mode="markers",
            marker={
                "size": marker_sizes,
                "color": [color_map.get(level, theme["secondary"]) for level in map_data["attention_level"]],
                "symbol": [
                    "diamond" if level == "優先檢視" else "square" if level == "持續觀察" else "circle"
                    for level in map_data["attention_level"]
                ],
                "line": {"color": theme["text"], "width": 1},
                "opacity": 0.94,
            },
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "%{customdata[1]}<br>"
                "目前 AQI: %{customdata[2]:.1f}<br>"
                "PM2.5: %{customdata[3]:.1f}<br>"
                "關注程度: %{customdata[4]}<br>"
                "點選此站即可套用篩選<extra></extra>"
            ),
            showlegend=False,
        )
    )
    figure.update_layout(
        paper_bgcolor=theme["card"],
        plot_bgcolor=theme["card"],
        font={"color": theme["text"]},
        margin={"l": 0, "r": 0, "t": 8, "b": 0},
        height=430,
        showlegend=False,
        clickmode="event+select",
        dragmode=False,
    )
    figure.update_xaxes(
        range=[119.75, 122.25],
        visible=False,
        fixedrange=True,
        showgrid=False,
        zeroline=False,
    )
    figure.update_yaxes(
        range=[21.65, 25.55],
        visible=False,
        fixedrange=True,
        showgrid=False,
        zeroline=False,
        scaleanchor="x",
        scaleratio=1,
    )
    return figure


def _render_station_map(brief: pd.DataFrame, theme: dict[str, str], selected_site_display: str) -> None:
    figure = _build_station_map(brief, theme)
    if figure is None:
        st.info("目前資料沒有可對照座標的測站，因此無法顯示地圖。")
        return
    event = st.plotly_chart(
        figure,
        width="stretch",
        theme=None,
        key="station_map_selector",
        on_select="rerun",
        selection_mode="points",
        config={"displaylogo": False, "scrollZoom": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
    )
    selected_points = getattr(getattr(event, "selection", None), "points", []) if event is not None else []
    if not selected_points:
        return
    map_site = selected_points[0].get("customdata", [None])[0]
    if map_site and map_site != selected_site_display:
        st.session_state["pending_station_filter"] = str(map_site)
        st.rerun()


def main() -> None:
    if st is None:
        print("需要安裝 Streamlit 才能啟動 Dashboard，請執行：pip install -r requirements.txt")
        return
    if px is None:
        st.error("目前缺少 Plotly，請先執行：pip install -r requirements.txt")
        return

    st.set_page_config(page_title="台灣 AQI 監測與預測", layout="wide")
    pending_station_filter = st.session_state.pop("pending_station_filter", None)
    if pending_station_filter:
        st.session_state["station_filter"] = pending_station_filter
    config = load_config()
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-mark">AQI</div>
                <div>
                    <strong>環境監測</strong>
                    <span>AQI / 空氣品質資料</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.header("主題設定")
        selected_theme_name = st.selectbox(
            "選擇深色主題",
            options=list(THEME_OPTIONS.keys()),
            index=list(THEME_OPTIONS.keys()).index(DEFAULT_THEME_NAME),
            format_func=lambda name: THEME_OPTIONS[name]["label"],
        )
    theme = get_theme(selected_theme_name)
    theme_validation = validate_theme_contrast(theme)
    fallback_theme_used = False
    if not theme_validation["passed"]:
        theme = get_theme(DEFAULT_THEME_NAME)
        fallback_theme_used = True
    inject_global_css(theme)
    if fallback_theme_used:
        st.warning("目前主題部分顏色對比不足，已使用預設主題。")

    data = load_dashboard_data(config)
    features = data["features"]
    predictions = data["predictions"]
    anomalies = data["anomalies"]
    events = data["events"]
    source_code = infer_data_source(config, features)
    data_source = _display_source(source_code)
    date_limits = _safe_date_range(features)

    latest_global_time = features["datetime"].max() if not features.empty and "datetime" in features else None
    global_observation_status = format_observation_status(latest_global_time, source_code)

    st.markdown(
        f"""
        <div class="hero-band">
          <div class="hero-copy">
            <div class="hero-kicker">
              <span>空氣品質監測</span>
              <span class="status-pill"><span class="status-dot"></span>{escape(_source_caption(source_code))}</span>
            </div>
            <h1>台灣 AQI 監測與預測</h1>
            <p>以測站歷史脈絡排序污染異常，並檢視下一小時 AQI 預測與資料品質。</p>
          </div>
          <div class="hero-meta">
            <span class="hero-meta-item">預測週期 <strong>下一小時</strong></span>
            <span class="hero-meta-item">資料來源 <strong>{escape(_display_source(source_code))}</strong></span>
            <span class="hero-meta-item">最新資料時點 <strong>{escape(global_observation_status["value"])}</strong></span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if features.empty:
        st.warning("尚未產生資料，請先執行 run_project.bat 或 python run_all.py --mode sample。")
        st.stop()

    predictor_model_path = resolve_path(config, "models.predictor")
    anomaly_model_path = resolve_path(config, "models.anomaly_detector")
    if not predictor_model_path.exists() or not anomaly_model_path.exists():
        st.warning("目前找不到模型檔案，Dashboard 仍可顯示既有資料；若要重建模型請執行完整流程。")

    with st.sidebar:
        st.header("篩選條件")
        county_options = ["全部縣市"]
        if "county_display" in features.columns:
            county_options += sorted(features["county_display"].dropna().astype(str).unique().tolist())
        selected_county = st.selectbox("縣市", county_options)
        county_filter = None if selected_county == "全部縣市" else selected_county

        site_base = features
        if county_filter and "county_display" in site_base.columns:
            site_base = site_base[site_base["county_display"] == county_filter]
        lookup = _site_lookup(site_base)
        site_options = ["全部測站", *lookup["site_name_display"].dropna().astype(str).tolist()]
        if st.session_state.get("station_filter") not in site_options:
            st.session_state["station_filter"] = "全部測站"
        selected_site_display = st.selectbox("測站", site_options, key="station_filter")
        selected_site = None
        if selected_site_display != "全部測站" and not lookup.empty:
            match = lookup[lookup["site_name_display"].astype(str) == selected_site_display]
            selected_site = str(match.iloc[0]["site_name"]) if not match.empty else selected_site_display

        if date_limits:
            date_range = st.date_input(
                "日期區間",
                date_limits,
                min_value=date_limits[0],
                max_value=date_limits[1],
            )
        else:
            date_range = None

    start_date = date_range[0] if isinstance(date_range, tuple) and len(date_range) == 2 else None
    end_date = date_range[1] if isinstance(date_range, tuple) and len(date_range) == 2 else None
    filtered_features = filter_by_site_and_date(
        features,
        site_name=selected_site,
        county_display=county_filter,
        start_datetime=start_date,
        end_datetime=end_date,
    )
    filtered_predictions = filter_by_site_and_date(
        predictions,
        site_name=selected_site,
        county_display=county_filter,
        start_datetime=start_date,
        end_datetime=end_date,
    )
    filtered_anomalies = filter_by_site_and_date(
        anomalies,
        site_name=selected_site,
        county_display=county_filter,
        start_datetime=start_date,
        end_datetime=end_date,
    )
    filtered_events = filter_by_site_and_date(
        events,
        site_name=selected_site,
        county_display=county_filter,
        start_datetime=start_date,
        end_datetime=end_date,
    )
    map_features = filter_by_site_and_date(
        features,
        county_display=county_filter,
        start_datetime=start_date,
        end_datetime=end_date,
    )
    map_predictions = filter_by_site_and_date(
        predictions,
        county_display=county_filter,
        start_datetime=start_date,
        end_datetime=end_date,
    )
    map_anomalies = filter_by_site_and_date(
        anomalies,
        county_display=county_filter,
        start_datetime=start_date,
        end_datetime=end_date,
    )
    comparison_features = filter_by_site_and_date(
        features,
        start_datetime=start_date,
        end_datetime=end_date,
    )
    comparison_predictions = filter_by_site_and_date(
        predictions,
        start_datetime=start_date,
        end_datetime=end_date,
    )
    comparison_anomalies = filter_by_site_and_date(
        anomalies,
        start_datetime=start_date,
        end_datetime=end_date,
    )

    quality = data_quality_summary(filtered_features)
    with st.sidebar:
        with st.expander("資料摘要", expanded=False):
            st.markdown(
                f"""<dl class="sidebar-summary">
                <div><dt>資料筆數</dt><dd>{quality['rows']:,}</dd></div>
                <div><dt>缺失值</dt><dd>{quality['missing_cells']:,}</dd></div>
                <div><dt>測站數</dt><dd>{quality['site_count']:,}</dd></div>
                <div><dt>日期範圍</dt><dd>{escape(str(quality['date_range']))}</dd></div>
                <div><dt>資料來源</dt><dd>{escape(data_source)}</dd></div>
                </dl>""",
                unsafe_allow_html=True,
            )

    selection_label = selected_site_display
    if selected_site_display == "全部測站" and selected_county != "全部縣市":
        selection_label = selected_county
    consumer_summary = build_consumer_summary(
        filtered_features,
        filtered_anomalies,
        source_code,
        selection_label,
    )
    latest_filtered_time = (
        filtered_features["datetime"].max()
        if not filtered_features.empty and "datetime" in filtered_features
        else None
    )
    download_date = (
        pd.to_datetime(latest_filtered_time).strftime("%Y%m%d")
        if latest_filtered_time is not None and not pd.isna(latest_filtered_time)
        else "no-data"
    )
    with st.sidebar:
        with st.expander("下載", expanded=False):
            st.download_button(
                "下載目前篩選資料 (.csv)",
                data=export_csv_bytes(filtered_features),
                file_name=f"taiwan_aqi_{download_date}.csv",
                mime="text/csv",
                use_container_width=True,
                disabled=filtered_features.empty,
            )
            st.download_button(
                "下載監測摘要 (.txt)",
                data=consumer_summary.encode("utf-8-sig"),
                file_name=f"taiwan_aqi_summary_{download_date}.txt",
                mime="text/plain",
                use_container_width=True,
                disabled=filtered_features.empty,
            )
            st.caption("匯出內容只包含目前篩選後的公開觀測欄位，不含模型內部特徵。")
    kpis = compute_kpis(filtered_features, filtered_anomalies)
    category, _category_color = aqi_category(float(kpis["latest_aqi"]))
    predictor_metrics = load_metrics(resolve_path(config, "reports.metrics_dir") / "predictor_metrics.json")
    anomaly_metrics = load_metrics(resolve_path(config, "reports.metrics_dir") / "anomaly_metrics.json")
    backtest_metrics = load_metrics(resolve_path(config, "reports.metrics_dir") / "backtest_metrics.json")
    confidence_metrics = load_metrics(resolve_path(config, "reports.confidence_file"))
    data_health = load_metrics(resolve_path(config, "reports.metrics_dir") / "data_health.json")
    evaluation_summary = load_metrics(resolve_path(config, "reports.metrics_dir") / "evaluation_summary.json")

    station_count = filtered_features["site_name_display"].nunique() if "site_name_display" in filtered_features else 0
    latest_note = "最新時點平均" if selected_site is None else selected_site_display
    signal_items = [
        ("平均 AQI", kpis["avg_aqi"], "目前篩選範圍", "calm"),
        ("最新 PM2.5", kpis["latest_pm25"], "μg/m³", "accent"),
        ("異常觀測", kpis["anomaly_count"], "模型與規則綜合", "alert"),
        ("資料筆數", len(filtered_features), data_source, "calm"),
        ("測站數", station_count, "目前篩選範圍", "calm"),
        ("資料狀態", data_health.get("status", "尚未評估"), "完整資料可靠性檢查", "calm"),
    ]
    st.markdown(
        f"""
        <div class="dashboard-intro">
            <span><strong>監測摘要</strong>　以目前篩選結果建立今日的工作優先序。</span>
            <span>{escape(data_source)} · {len(filtered_features):,} 筆資料</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    signal_deck(kpis["latest_aqi"], category, latest_note, signal_items)
    activity_guidance_panel(kpis["latest_aqi"], source_code, latest_filtered_time)

    overview_tab, comparison_tab, prediction_tab, anomaly_tab, quality_tab, metrics_tab = st.tabs(
        ["總覽", "地區比較", "預測", "異常偵測", "資料品質", "模型指標"]
    )

    with overview_tab:
        risk_brief = build_station_risk_brief(
            filtered_features,
            reference_features=features,
            predictions=filtered_predictions,
            anomalies=filtered_anomalies,
            policy=config.get("risk_policy"),
        )
        map_risk_brief = build_station_risk_brief(
            map_features,
            reference_features=features,
            predictions=map_predictions,
            anomalies=map_anomalies,
            policy=config.get("risk_policy"),
        )
        map_column, queue_column = st.columns([1.3, 0.7], gap="large")
        with map_column:
            section_header("地圖篩選", "台灣測站分布", "點選測站同步更新篩選條件")
            _render_station_map(map_risk_brief, theme, selected_site_display)
            st.markdown(
                '<p class="map-selection-note">標記大小代表 AQI；圓形、方形與菱形分別代表一般監測、持續觀察與優先檢視。</p>',
                unsafe_allow_html=True,
            )
        with queue_column:
            section_header("工作優先序", "先檢視哪些測站", "本站基準、預測與異常訊號")
            _render_risk_brief(risk_brief)
            _render_priority_queue(risk_brief)
            with st.expander("檢視完整測站判讀", expanded=False):
                render_table(
                    _risk_brief_table(risk_brief),
                    empty_message="目前沒有可排序的測站資料。",
                    label="測站脈絡風險排序表",
                )

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        section_header("趨勢監測", "AQI 與 PM2.5 變化", "依目前選取的地區、測站與日期範圍呈現")
        left, right = st.columns([1.15, 1], gap="large")
        with left:
            st.subheader("AQI 趨勢")
            if filtered_features.empty:
                st.info("目前篩選條件下沒有 AQI 資料。")
            else:
                color_col = "site_name_display" if selected_site_display == "全部測站" else None
                fig = px.line(
                    filtered_features,
                    x="datetime",
                    y="aqi",
                    color=color_col,
                    hover_data=[col for col in ["county_display", "site_name_display", "pm25"] if col in filtered_features],
                    labels=DISPLAY_COLUMN_MAP,
                    color_discrete_sequence=chart_color_sequence(theme),
                )
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=400)
                fig = apply_plotly_theme(fig, theme)
                _plot_chart(fig)
        with right:
            st.subheader("PM2.5 趨勢")
            if filtered_features.empty:
                st.info("目前篩選條件下沒有 PM2.5 資料。")
            else:
                color_col = "site_name_display" if selected_site_display == "全部測站" else None
                fig = px.line(
                    filtered_features,
                    x="datetime",
                    y="pm25",
                    color=color_col,
                    hover_data=[col for col in ["county_display", "site_name_display", "aqi"] if col in filtered_features],
                    labels=DISPLAY_COLUMN_MAP,
                    color_discrete_sequence=chart_color_sequence(theme),
                )
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=400)
                fig = apply_plotly_theme(fig, theme)
                _plot_chart(fig)

    with comparison_tab:
        st.markdown(
            '<div class="section-note">同時比較 2–3 個測站的目前 AQI、下一小時預測與資料時點；此分頁不受側欄單站篩選限制，但會沿用日期區間。</div>',
            unsafe_allow_html=True,
        )
        latest_station_rows = pd.DataFrame()
        if not comparison_features.empty and {"site_name_display", "site_name", "datetime", "aqi"}.issubset(comparison_features.columns):
            latest_station_rows = (
                comparison_features.sort_values(["site_name", "datetime"])
                .groupby("site_name", sort=False, as_index=False)
                .tail(1)
                .sort_values("aqi", ascending=False)
            )
        comparison_options = (
            sorted(latest_station_rows["site_name_display"].dropna().astype(str).unique().tolist())
            if not latest_station_rows.empty
            else []
        )
        default_comparison_sites = (
            latest_station_rows["site_name_display"].dropna().astype(str).drop_duplicates().head(3).tolist()
            if not latest_station_rows.empty
            else []
        )
        selected_comparison_sites = st.multiselect(
            "比較測站（最多 3 個）",
            options=comparison_options,
            default=default_comparison_sites,
            max_selections=3,
        )
        comparison = pd.DataFrame()
        if len(selected_comparison_sites) < 2:
            st.info("請至少選擇 2 個測站，才能建立可比較的決策摘要。")
        else:
            comparison = build_station_comparison(
                comparison_features,
                comparison_predictions,
                comparison_anomalies,
                selected_comparison_sites,
                reference_features=features,
            )
            recommendation = choose_recommended_station(comparison)
            if comparison.empty or recommendation["site_name"] is None:
                st.info("目前選取的測站沒有足夠且時點可比的資料。")
            else:
                recommendation_site = escape(str(recommendation["site_name_display"]))
                recommendation_basis = escape(str(recommendation["basis"]))
                recommendation_value = escape(_format_optional_number(recommendation["value"]))
                st.markdown(
                    f"""
                    <section class="comparison-recommendation" aria-label="目前較佳選擇">
                        <div><span>目前較佳選擇</span><strong>{recommendation_site}</strong></div>
                        <div class="comparison-recommendation-value">{recommendation_basis} {recommendation_value}</div>
                    </section>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown(comparison_cards_html(comparison), unsafe_allow_html=True)

                chart_column, trend_column = st.columns(2, gap="large")
                with chart_column:
                    st.subheader("目前與下一小時")
                    chart_data = comparison[
                        ["site_name_display", "current_aqi", "predicted_next_hour_aqi"]
                    ].melt(id_vars="site_name_display", var_name="series", value_name="aqi").dropna(subset=["aqi"])
                    chart_data["series"] = chart_data["series"].replace(
                        {"current_aqi": "目前 AQI", "predicted_next_hour_aqi": "下一小時預測"}
                    )
                    fig = px.bar(
                        chart_data,
                        x="site_name_display",
                        y="aqi",
                        color="series",
                        barmode="group",
                        labels={"site_name_display": "測站", "aqi": "AQI", "series": "資料"},
                        color_discrete_sequence=[theme["primary"], theme["secondary"]],
                    )
                    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=330)
                    _plot_chart(apply_plotly_theme(fig, theme))
                with trend_column:
                    st.subheader("近 24 小時 AQI")
                    newest_selected_time = pd.to_datetime(comparison["observed_at"], errors="coerce").max()
                    trend_data = comparison_features[
                        comparison_features["site_name_display"].astype(str).isin(selected_comparison_sites)
                    ].copy()
                    if pd.notna(newest_selected_time):
                        trend_data = trend_data[
                            (trend_data["datetime"] >= newest_selected_time - pd.Timedelta(hours=24))
                            & (trend_data["datetime"] <= newest_selected_time)
                        ]
                    fig = px.line(
                        trend_data,
                        x="datetime",
                        y="aqi",
                        color="site_name_display",
                        labels=DISPLAY_COLUMN_MAP,
                        color_discrete_sequence=chart_color_sequence(theme),
                    )
                    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=330)
                    _plot_chart(apply_plotly_theme(fig, theme))

                comparison_table_columns = [
                    "observed_at",
                    "county_display",
                    "site_name_display",
                    "freshness_state",
                    "current_aqi",
                    "aqi_category",
                    "pm25",
                    "predicted_next_hour_aqi",
                    "lower_80_aqi",
                    "upper_80_aqi",
                    "forecast_change",
                    "baseline_aqi",
                    "aqi_vs_baseline",
                    "recent_6h_change",
                    "attention_level",
                    "context_evidence",
                    "is_anomaly",
                    "anomaly_evidence",
                ]
                comparison_table = _rename_for_display(
                    _select_columns(comparison, comparison_table_columns)
                )
                if "是否異常" in comparison_table:
                    comparison_table["是否異常"] = comparison_table["是否異常"].map({True: "是", False: "否"})
                with st.expander("檢視完整比較資料", expanded=False):
                    render_table(comparison_table, label="測站比較資料表")
                st.download_button(
                    "下載測站比較資料 (.csv)",
                    data=export_comparison_csv(comparison),
                    file_name="taiwan_aqi_station_comparison.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        st.markdown(
            f'<div class="section-note">比較結果不是官方行程或健康建議。推薦會排除落後最新時點超過 2 小時的測站，並優先比較下一小時點預測；缺少預測時才使用目前 AQI。{escape(data_source)} 的限制仍適用。</div>',
            unsafe_allow_html=True,
        )
    with prediction_tab:
        st.markdown(
            '<div class="section-note">根據目前及過去資料估計同一測站下一小時 AQI；模型不會使用預測時點之後的資料。</div>',
            unsafe_allow_html=True,
        )
        if filtered_predictions.empty:
            st.info("找不到預測結果，請先執行完整 sample mode 流程。")
        else:
            prediction_plot = filtered_predictions.sort_values("datetime").copy()
            if selected_site is None:
                aggregate_columns = ["actual_next_hour_aqi", "predicted_next_hour_aqi"]
                aggregate_columns.extend(
                    column
                    for column in ["lower_80_aqi", "upper_80_aqi", "lower_95_aqi", "upper_95_aqi"]
                    if column in prediction_plot.columns
                )
                prediction_plot = prediction_plot.groupby("datetime", as_index=False)[aggregate_columns].mean()
            st.subheader("實際 AQI 與預測 AQI")
            line_cols = ["datetime", "actual_next_hour_aqi", "predicted_next_hour_aqi"]
            line_df = prediction_plot[line_cols].melt(id_vars="datetime", var_name="series", value_name="aqi")
            line_df["series"] = line_df["series"].replace(
                {
                    "actual_next_hour_aqi": "實際下一小時 AQI（實線）",
                    "predicted_next_hour_aqi": "預測下一小時 AQI（虛線）",
                }
            )
            fig = px.line(line_df, x="datetime", y="aqi", color="series", color_discrete_sequence=chart_color_sequence(theme))
            fig.for_each_trace(
                lambda trace: trace.update(
                    line={
                        "width": 2.4,
                        "dash": "dash" if "虛線" in str(trace.name) else "solid",
                    }
                )
            )
            if go is not None and {"lower_80_aqi", "upper_80_aqi"}.issubset(prediction_plot.columns):
                band_red, band_green, band_blue = hex_to_rgb(theme["secondary"])
                fig.add_trace(
                    go.Scatter(
                        x=prediction_plot["datetime"],
                        y=prediction_plot["upper_80_aqi"],
                        mode="lines",
                        line={"width": 0},
                        hoverinfo="skip",
                        showlegend=False,
                        name="80% 預測區間上界",
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=prediction_plot["datetime"],
                        y=prediction_plot["lower_80_aqi"],
                        mode="lines",
                        line={"width": 0},
                        fill="tonexty",
                        fillcolor=f"rgba({band_red}, {band_green}, {band_blue}, 0.18)",
                        hoverinfo="skip",
                        name="80% 經驗預測區間",
                    )
                )
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=360, xaxis_title="時間", yaxis_title="AQI")
            fig = apply_plotly_theme(fig, theme)
            _plot_chart(fig)

            confidence_table = _confidence_summary_table(confidence_metrics)
            confidence_columns = {"lower_80_aqi", "upper_80_aqi", "lower_95_aqi", "upper_95_aqi"}
            if confidence_table.empty or not confidence_columns.issubset(filtered_predictions.columns):
                st.info("尚無預測可信度產物；請重新執行 sample pipeline 以建立經驗預測區間。")
            else:
                section_header("可信度", "預測區間與跨級監測", "歷史預測誤差校準 · 顯示合理波動範圍")
                intervals = confidence_metrics.get("intervals", {})
                confidence_columns_ui = st.columns(4, gap="large")
                coverage_80 = intervals.get("80", {}).get("empirical_coverage")
                coverage_95 = intervals.get("95", {}).get("empirical_coverage")
                width_80 = intervals.get("80", {}).get("mean_width")
                confidence_columns_ui[0].metric("80% 實際覆蓋率", "N/A" if coverage_80 is None else f"{float(coverage_80) * 100:.1f}%")
                confidence_columns_ui[1].metric("95% 實際覆蓋率", "N/A" if coverage_95 is None else f"{float(coverage_95) * 100:.1f}%")
                confidence_columns_ui[2].metric("80% 平均寬度", "N/A" if width_80 is None else f"{float(width_80):.1f} AQI")
                confidence_columns_ui[3].metric("校準殘差", f"{int(confidence_metrics.get('calibration_rows', 0)):,} 筆")

                watch_table = _threshold_watch_table(filtered_predictions)
                st.subheader("AQI 跨級關注")
                if watch_table.empty:
                    st.success("目前篩選範圍的 95% 預測區間未跨過下一個 AQI 分級門檻。")
                else:
                    st.markdown(_threshold_watch_cards_html(watch_table), unsafe_allow_html=True)
                    with st.expander("檢視完整跨級清單", expanded=False):
                        render_table(
                            watch_table.head(30),
                            label="AQI 預測區間跨級關注表",
                            table_class="confidence-watch-table",
                        )
                with st.expander("檢視區間校準摘要", expanded=False):
                    render_table(confidence_table, label="預測區間校準摘要")
                st.caption("區間來自歷史 rolling-origin 誤差的經驗校準，不代表保證機率，也不是官方警報或健康風險判定。")

            st.subheader("預測誤差")
            error_df = prediction_plot.copy()
            error_df["prediction_error"] = error_df["predicted_next_hour_aqi"] - error_df["actual_next_hour_aqi"]
            error_df["absolute_error"] = error_df["prediction_error"].abs()
            error_df["error_direction"] = error_df["prediction_error"].ge(0).map({True: "高估", False: "低估"})
            fig = px.bar(
                error_df,
                x="datetime",
                y="prediction_error",
                color="error_direction",
                hover_data=[col for col in ["county_display", "site_name_display", "absolute_error"] if col in error_df],
                labels={**DISPLAY_COLUMN_MAP, "error_direction": "誤差方向"},
                color_discrete_map={"高估": theme["accent"], "低估": theme["secondary"]},
            )
            fig.add_hline(y=0, line_width=1, line_color=theme["muted_text"])
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=280)
            fig = apply_plotly_theme(fig, theme)
            _plot_chart(fig)

        predictor_table = _model_metrics_table(predictor_metrics)
        st.subheader("模型比較")
        if predictor_table.empty:
            st.info("找不到預測模型評估指標，請先執行評估流程。")
        else:
            render_table(predictor_table)
        if predictor_metrics:
            p_cols = st.columns(3)
            p_cols[0].metric("MAE", predictor_metrics.get("mae", "N/A"))
            p_cols[1].metric("RMSE", predictor_metrics.get("rmse", "N/A"))
            p_cols[2].metric("R2", predictor_metrics.get("r2", "N/A"))
            split_rows = predictor_metrics.get("split_rows", {})
            if split_rows:
                st.caption(
                    "模型以時間順序切分："
                    f"訓練 {split_rows.get('train', 0):,} 筆、"
                    f"驗證 {split_rows.get('validation', 0):,} 筆、"
                    f"最終測試 {split_rows.get('final_test', 0):,} 筆。"
                )

        st.subheader("滾動回測")
        backtest_table = _backtest_aggregate_table(backtest_metrics)
        if backtest_table.empty:
            st.info("尚無滾動回測結果；請先執行 sample pipeline。")
        else:
            fold_count = int(backtest_metrics.get("fold_count", 0))
            st.caption(f"{fold_count} 個測試窗皆只使用更早資料訓練，用於檢查不同時間段的穩定性。")
            render_table(backtest_table, label="滾動回測模型比較")

    with anomaly_tab:
        st.markdown(
            '<div class="section-note">系統整合污染門檻與近期變化，標示值得人工確認的觀測。每筆事件都保留觸發依據，但不代表污染來源已被確認。</div>',
            unsafe_allow_html=True,
        )
        st.subheader("事件調查摘要")
        if filtered_events.empty:
            st.info("目前篩選範圍沒有可合併的異常事件。")
        else:
            event_cols = st.columns(3)
            event_cols[0].metric("異常事件", f"{len(filtered_events):,}")
            event_cols[1].metric("最長持續", f"{int(filtered_events['duration_hours'].max()):,} 小時")
            event_cols[2].metric("最高事件 AQI", f"{float(filtered_events['peak_aqi'].max()):.0f}")
            event_columns = [
                "datetime",
                "end_datetime",
                "county_display",
                "site_name_display",
                "duration_hours",
                "peak_aqi",
                "peak_pm25",
                "evidence_summary",
            ]
            render_table(
                _rename_for_display(_select_columns(filtered_events.head(10), event_columns)),
                label="優先檢視的異常事件",
            )
        if filtered_anomalies.empty:
            st.info("找不到異常偵測結果，請先執行完整 sample mode 流程。")
        else:
            st.subheader("AQI 趨勢與異常標記")
            anomaly_events = filtered_anomalies[filtered_anomalies["is_anomaly"] == 1].copy()
            if anomaly_events.empty:
                st.info("目前篩選範圍沒有偵測到異常事件。")
            else:
                anomaly_timeline = filtered_anomalies.sort_values("datetime").copy()
                if selected_site is None:
                    anomaly_baseline = anomaly_timeline.groupby("datetime", as_index=False)["aqi"].mean()
                    baseline_name = "測站平均 AQI（實線）"
                else:
                    anomaly_baseline = anomaly_timeline[["datetime", "aqi"]]
                    baseline_name = f"{selected_site_display} AQI（實線）"
                fig = px.line(
                    anomaly_baseline,
                    x="datetime",
                    y="aqi",
                    labels=DISPLAY_COLUMN_MAP,
                    color_discrete_sequence=[theme["primary"]],
                )
                fig.update_traces(name=baseline_name, line={"width": 2.2})
                marker_fig = px.scatter(
                    anomaly_events,
                    x="datetime",
                    y="aqi",
                    hover_data=[col for col in ["county_display", "site_name_display", "pm25", "anomaly_score"] if col in anomaly_events],
                    labels=DISPLAY_COLUMN_MAP,
                    color_discrete_sequence=[theme["danger"]],
                )
                for trace in marker_fig.data:
                    trace.update(
                        name="異常事件（菱形）",
                        marker={"size": 10, "symbol": "diamond", "line": {"width": 1, "color": theme["text"]}},
                    )
                    fig.add_trace(trace)
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=340)
                fig = apply_plotly_theme(fig, theme)
                _plot_chart(fig)

            left, right = st.columns([1.15, 1], gap="large")
            with left:
                st.subheader("高風險異常事件")
                top_cases = anomaly_events.sort_values(["anomaly_score", "aqi"], ascending=False)
                top_cases["anomaly_evidence"] = top_cases.apply(describe_anomaly_evidence, axis=1)
                display_cols = [
                    "datetime",
                    "site_name_display",
                    "aqi",
                    "pm25",
                    "anomaly_evidence",
                ]
                table = _rename_for_display(_select_columns(top_cases.head(15), display_cols)).rename(
                    columns={"anomaly_evidence": "異常證據"}
                )
                if "時間" in table.columns:
                    table["時間"] = pd.to_datetime(table["時間"], errors="coerce").dt.strftime("%m/%d %H:%M")
                if "測站" in table.columns:
                    table["測站"] = table["測站"].astype(str).str.replace(r"測站$", "", regex=True)
                render_table(table, label="高風險異常事件表", table_class="anomaly-case-table")
            with right:
                st.subheader("各測站異常數")
                station_col = "site_name_display" if "site_name_display" in filtered_anomalies.columns else "site_name"
                count_by_station = filtered_anomalies.groupby(station_col, as_index=False)["is_anomaly"].sum()
                fig = px.bar(
                    count_by_station,
                    x=station_col,
                    y="is_anomaly",
                    labels=DISPLAY_COLUMN_MAP,
                    color_discrete_sequence=[theme["danger"]],
                )
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=300, xaxis_title="測站", yaxis_title="異常數")
                fig = apply_plotly_theme(fig, theme)
                _plot_chart(fig)

        with st.expander("了解異常判讀方法", expanded=False):
            st.markdown(
                "達到規則門檻代表 AQI > 100、PM2.5 > 35，或 AQI 高於該站 12 小時移動平均加上 "
                "2.5 個標準差；Z-score 用於判斷近期偏離，Isolation Forest 用於辨識多變量型態偏離。"
            )
            st.caption("目前以規則產生 pseudo-label，precision、recall 與 F1 不等同真實污染事件準確率；正式應用仍需人工事件標註。")

    with quality_tab:
        st.markdown(
            '<div class="section-note">此頁整理資料完整性、缺失值與來源摘要，協助快速判斷目前資料是否適合分析。</div>',
            unsafe_allow_html=True,
        )
        q_cols_top = st.columns(3, gap="large")
        with q_cols_top[0]:
            metric_card("資料筆數", quality["rows"])
        with q_cols_top[1]:
            metric_card("缺失值", quality["missing_cells"])
        with q_cols_top[2]:
            metric_card("測站數", quality["site_count"])

        st.markdown('<div class="metric-row-spacer"></div>', unsafe_allow_html=True)
        q_cols_bottom = st.columns(2, gap="large")
        with q_cols_bottom[0]:
            metric_card("日期範圍", quality["date_range"])
        with q_cols_bottom[1]:
            metric_card("資料來源", data_source)

        st.subheader("資料可靠性")
        health_cols = st.columns(4, gap="large")
        health_cols[0].metric("分析狀態", data_health.get("status", "尚未評估"))
        health_cols[1].metric("重複時間點", data_health.get("duplicate_station_timestamps", "N/A"))
        health_cols[2].metric("延遲測站", data_health.get("stale_station_count", "N/A"))
        largest_gap = data_health.get("largest_gap_hours")
        health_cols[3].metric("最大間隔", "N/A" if largest_gap is None else f"{float(largest_gap):g} 小時")
        st.caption("可靠性檢查以完整特徵資料計算，包含站點時間戳重複、測站更新延遲與最大觀測間隔。")

        st.subheader("各欄位缺失值")
        missing_table = filtered_features.isna().sum().reset_index()
        missing_table.columns = ["欄位", "缺失值數量"]
        missing_table["欄位"] = missing_table["欄位"].replace(DISPLAY_COLUMN_MAP)
        missing_cells = int(missing_table["缺失值數量"].sum())
        if missing_cells == 0:
            st.success("欄位完整性通過：目前篩選資料沒有缺失值。")
        with st.expander("檢視欄位缺失統計", expanded=missing_cells > 0):
            render_table(missing_table, label="各欄位缺失值")

        st.subheader("近期資料樣本")
        sample_cols = ["datetime", "county_display", "site_name_display", "aqi", "pm25", "pm10", "o3", "co", "wind_speed"]
        with st.expander("檢視最近 20 筆資料", expanded=False):
            render_table(_rename_for_display(_select_columns(filtered_features.tail(20), sample_cols)), label="近期資料樣本")

    with metrics_tab:
        st.markdown(
            '<div class="section-note">此頁整理預測與異常偵測指標。異常偵測 precision、recall、F1 是對 pseudo-label 評估，不代表真實污染事件準確率。</div>',
            unsafe_allow_html=True,
        )
        st.subheader("AQI 預測模型")
        predictor_table = _model_metrics_table(predictor_metrics)
        if predictor_table.empty:
            st.info("找不到預測模型評估檔，請先執行完整 sample mode 流程。")
        else:
            render_table(predictor_table)

        st.subheader("時間序列穩定性")
        backtest_table = _backtest_aggregate_table(backtest_metrics)
        if backtest_table.empty:
            st.info("尚無滾動回測結果。")
        else:
            render_table(backtest_table, label="滾動回測平均表現")

        st.subheader("異常偵測模型")
        anomaly_table = _model_metrics_table(anomaly_metrics)
        if anomaly_table.empty:
            st.info("找不到異常偵測評估檔，請先執行完整 sample mode 流程。")
        else:
            render_table(anomaly_table)
        if anomaly_metrics:
            a_cols = st.columns(3)
            a_cols[0].metric("Precision", anomaly_metrics.get("precision", "N/A"))
            a_cols[1].metric("Recall", anomaly_metrics.get("recall", "N/A"))
            a_cols[2].metric("F1", anomaly_metrics.get("f1", "N/A"))

        if evaluation_summary:
            st.subheader("評估摘要")
            summary_rows = [
                {"項目": "特徵資料筆數", "內容": str(evaluation_summary.get("rows", {}).get("features", "N/A"))},
                {"項目": "預測資料筆數", "內容": str(evaluation_summary.get("rows", {}).get("predictions", "N/A"))},
                {"項目": "異常資料筆數", "內容": str(evaluation_summary.get("rows", {}).get("anomaly_results", "N/A"))},
                {"項目": "測站數", "內容": str(evaluation_summary.get("site_count", "N/A"))},
                {"項目": "起始時間", "內容": str(evaluation_summary.get("datetime_range", {}).get("start", "N/A"))},
                {"項目": "結束時間", "內容": str(evaluation_summary.get("datetime_range", {}).get("end", "N/A"))},
            ]
            render_table(pd.DataFrame(summary_rows))

        st.markdown(
            '<div class="section-note">限制：Sample Data 是模擬資料；API 欄位格式可能變動；異常偵測目前沒有人工標註 ground truth。未來可接入排程 API、真實事件標註與更嚴格的時間序列交叉驗證。</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f"""
        <div class="dashboard-footer">
            <span>環境監測資料工作台</span>
            <span>測站脈絡判讀 · 下一小時預測 · {escape(data_source)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
