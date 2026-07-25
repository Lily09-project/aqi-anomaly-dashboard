from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd

from src.app_helpers import (
    aqi_category,
    compute_kpis,
    data_quality_summary,
    filter_by_site_and_date,
    infer_data_source,
    load_dashboard_data,
    load_metrics,
)
from src.theme import DEFAULT_THEME_NAME, THEME, THEME_OPTIONS, chart_color_sequence, get_theme, validate_theme_contrast
from src.utils import load_config, resolve_path


try:
    import plotly.express as px  # type: ignore
except Exception:  # pragma: no cover
    px = None

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
    "absolute_error": "絕對誤差",
    "is_anomaly": "是否異常",
    "anomaly_score": "異常分數",
    "pseudo_anomaly": "規則式標籤",
    "zscore_anomaly": "Z-score 異常",
    "isolation_forest_anomaly": "Isolation Forest 異常",
    "timestamp": "時間",
    "station_id": "站點編號",
    "station_name": "站點名稱",
    "district": "行政區",
    "total_capacity": "總車位",
    "available_bikes": "可借車輛",
    "available_spaces": "可還空位",
    "status": "站點狀態",
    "occupancy_rate": "使用率",
    "target_next_available_bikes": "下一時間點可借車輛",
    "predicted_available_bikes": "預測可借車輛",
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
            background: var(--surface);
            color: var(--text);
            padding: 1.4rem 1.55rem 1.35rem;
            border: 1px solid var(--border);
            border-top: 3px solid var(--accent);
            border-radius: 8px;
            margin-bottom: 1.45rem;
            box-shadow: 0 12px 28px var(--shadow);
        }}
        .hero-kicker, .hero-meta {{
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.55rem;
        }}
        .hero-kicker {{
            color: var(--muted-text);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.08em;
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
            font-size: 0.7rem;
        }}
        .hero-band h1 {{
            color: var(--text) !important;
            margin: 0.6rem 0 0.45rem;
        }}
        .hero-band p {{
            max-width: 72ch;
            margin: 0.35rem 0;
            color: var(--muted-text) !important;
        }}
        .hero-meta {{
            margin-top: 1rem;
            padding-top: 0.8rem;
            border-top: 1px solid var(--border);
            color: var(--muted-text);
            font-size: 0.82rem;
        }}
        .hero-meta-item {{
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.4rem 0.65rem;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 6px;
        }}
        .hero-meta-item strong {{ color: var(--text); }}
        .status-pill {{
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            padding: 0.38rem 0.65rem;
            border-radius: 6px;
            background: var(--accent-soft);
            border: 1px solid var(--accent);
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
            box-shadow: 0 0 0 3px var(--success-soft);
        }}
        .metric-card,
        .kpi-card {{
            background: var(--card);
            color: var(--text);
            border: 1px solid var(--border);
            border-left: 4px solid var(--accent);
            border-radius: 8px;
            padding: 1rem 1.05rem;
            min-height: 112px;
            height: calc(100% - 14px);
            box-shadow: 0 8px 20px var(--shadow);
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
        @media (max-width: 900px) {{
            .block-container {{ padding: 1.5rem 1.35rem 3rem; }}
            h1 {{ font-size: 2rem !important; }}
            .section-header {{ align-items: start; flex-direction: column; gap: 0.25rem; }}
            .section-context {{ text-align: left; }}
        }}
        @media (max-width: 640px) {{
            .block-container {{ padding: 3.75rem 0.9rem 2.5rem; }}
            h1 {{ font-size: 1.75rem !important; }}
            h2 {{ font-size: 1.25rem !important; }}
            .hero-band {{ padding: 1.15rem 1rem 1.05rem; margin-bottom: 1rem; }}
            .hero-band p {{ font-size: 1rem; }}
            .hero-kicker, .status-pill {{ font-size: 0.84rem; }}
            .hero-meta {{ align-items: stretch; flex-direction: column; }}
            .hero-meta-item, .status-pill {{
                width: 100%;
                box-sizing: border-box;
                font-size: 0.9rem;
            }}
            .metric-card {{ min-height: 98px; padding: 0.9rem; }}
            .metric-card .value {{ font-size: 1.5rem; }}
            .metric-card .label {{ font-size: 0.9rem; }}
            .metric-card .note {{ font-size: 0.82rem; }}
            .section-note, .section-card {{ font-size: 0.95rem; }}
            section[data-testid="stSidebar"] [data-baseweb="select"],
            section[data-testid="stSidebar"] input {{
                font-size: 1rem !important;
            }}
            .table-shell {{ margin-left: -0.1rem; margin-right: -0.1rem; }}
            .dashboard-table {{ font-size: 0.84rem; }}
            .dashboard-table th, .dashboard-table td {{ padding: 0.58rem 0.55rem; }}
            .dashboard-footer {{ align-items: start; flex-direction: column; gap: 0.25rem; }}
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
    table_html = display.to_html(index=False, border=0, classes="dashboard-table", escape=True)
    st.markdown(
        f'<div class="table-shell" role="region" aria-label="{escape(label)}" tabindex="0">{table_html}</div>',
        unsafe_allow_html=True,
    )


def _display_source(source: str) -> str:
    return "API Data" if source == "API Data" else "Sample Data"


def _source_caption(source: str) -> str:
    return "環保署 API 資料" if source == "API Data" else "Sample Data（模擬資料）"


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


def main() -> None:
    if st is None:
        print("需要安裝 Streamlit 才能啟動 Dashboard，請執行：pip install -r requirements.txt")
        return
    if px is None:
        st.error("目前缺少 Plotly，請先執行：pip install -r requirements.txt")
        return

    st.set_page_config(page_title="台灣 AQI 預測 Dashboard", layout="wide")
    config = load_config()
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-mark">AQI</div>
                <div>
                    <strong>環境監測</strong>
                    <span>Prediction Dashboard</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.header("視覺主題")
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
    source_code = infer_data_source(config, features)
    data_source = _display_source(source_code)

    st.markdown(
        f"""
        <div class="hero-band">
          <div class="hero-kicker">
            <span>環境監測控制台</span>
            <span class="status-pill"><span class="status-dot"></span>{escape(_source_caption(source_code))}</span>
          </div>
          <h1>台灣 AQI 預測 Dashboard</h1>
          <p>以時間序列特徵預測下一小時 AQI，並追蹤可能的空氣污染異常。</p>
          <div class="hero-meta">
            <span class="hero-meta-item">預測任務 <strong>下一小時 AQI</strong></span>
            <span class="hero-meta-item">資料模式 <strong>{escape(_display_source(source_code))}</strong></span>
            <span class="hero-meta-item">展示用途 <strong>本地 Demo</strong></span>
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

    date_limits = _safe_date_range(features)

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
        selected_site_display = st.selectbox("測站", site_options)
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

    kpis = compute_kpis(filtered_features, filtered_anomalies)
    category, _category_color = aqi_category(float(kpis["latest_aqi"]))
    predictor_metrics = load_metrics(resolve_path(config, "reports.metrics_dir") / "predictor_metrics.json")
    anomaly_metrics = load_metrics(resolve_path(config, "reports.metrics_dir") / "anomaly_metrics.json")
    evaluation_summary = load_metrics(resolve_path(config, "reports.metrics_dir") / "evaluation_summary.json")

    station_count = filtered_features["site_name_display"].nunique() if "site_name_display" in filtered_features else 0
    latest_note = "最新時點平均" if selected_site is None else selected_site_display
    metric_items = [
        ("最新 AQI", kpis["latest_aqi"], latest_note),
        ("AQI 等級", category, "目前空氣品質"),
        ("平均 AQI", kpis["avg_aqi"], "目前篩選範圍"),
        ("最新 PM2.5", kpis["latest_pm25"], "μg/m³"),
        ("異常事件數", kpis["anomaly_count"], "模型與規則綜合"),
        ("資料筆數", len(filtered_features), data_source),
        ("測站數", station_count, "目前篩選範圍"),
    ]
    section_header("Overview", "目前空氣品質", f"{data_source} · {len(filtered_features):,} 筆資料")
    for items in (metric_items[:4], metric_items[4:]):
        columns = st.columns(len(items), gap="large")
        for column, (label, value, note) in zip(columns, items):
            with column:
                metric_card(label, value, note)

    overview_tab, prediction_tab, anomaly_tab, quality_tab, metrics_tab = st.tabs(
        ["總覽", "預測", "異常偵測", "資料品質", "模型指標"]
    )

    with overview_tab:
        st.markdown(
            '<div class="section-note">此頁用來快速檢查不同測站的 AQI 與 PM2.5 趨勢，所有測站與縣市皆使用中文顯示欄位。</div>',
            unsafe_allow_html=True,
        )
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
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=390)
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
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=390)
                fig = apply_plotly_theme(fig, theme)
                _plot_chart(fig)

    with prediction_tab:
        st.markdown(
            '<div class="section-note">預測任務是 next-hour nowcasting：使用當下與過去資料預測同一測站下一小時 AQI，並用時間序列切分避免資料洩漏。</div>',
            unsafe_allow_html=True,
        )
        if filtered_predictions.empty:
            st.info("找不到預測結果，請先執行完整 sample mode 流程。")
        else:
            prediction_plot = filtered_predictions.sort_values("datetime").copy()
            if selected_site is None:
                prediction_plot = prediction_plot.groupby("datetime", as_index=False)[
                    ["actual_next_hour_aqi", "predicted_next_hour_aqi"]
                ].mean()
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
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=360, xaxis_title="時間", yaxis_title="AQI")
            fig = apply_plotly_theme(fig, theme)
            _plot_chart(fig)

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

    with anomaly_tab:
        st.markdown(
            '<div class="section-note">異常偵測使用 AQI、PM2.5 與移動統計建立 pseudo-label，再用 Z-score 與 Isolation Forest 偵測可疑污染事件。</div>',
            unsafe_allow_html=True,
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
                display_cols = [
                    "datetime",
                    "county_display",
                    "site_name_display",
                    "aqi",
                    "pm25",
                    "anomaly_score",
                    "is_anomaly",
                    "pseudo_anomaly",
                    "zscore_anomaly",
                    "isolation_forest_anomaly",
                ]
                render_table(_rename_for_display(_select_columns(top_cases.head(15), display_cols)))
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

        st.markdown(
            '<div class="section-note">異常規則：AQI 高於 100、PM2.5 高於 35，或 AQI 高於該測站 12 小時移動平均加上 2.5 個標準差。這是 pseudo-label，正式應用仍需真實事件標註驗證。</div>',
            unsafe_allow_html=True,
        )

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

        st.subheader("各欄位缺失值")
        missing_table = filtered_features.isna().sum().reset_index()
        missing_table.columns = ["欄位", "缺失值數量"]
        missing_table["欄位"] = missing_table["欄位"].replace(DISPLAY_COLUMN_MAP)
        render_table(missing_table)

        st.subheader("資料樣本")
        sample_cols = ["datetime", "county_display", "site_name_display", "aqi", "pm25", "pm10", "o3", "co", "wind_speed"]
        render_table(_rename_for_display(_select_columns(filtered_features.tail(20), sample_cols)))

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
            <span>台灣 AQI Prediction Dashboard</span>
            <span>Next-hour forecasting · {escape(data_source)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
