from html import escape

import pandas as pd

from src.app_helpers import data_quality_summary
from src.dashboard.components import (
    DISPLAY_COLUMN_MAP,
    _backtest_aggregate_table,
    _confidence_summary_table,
    _format_optional_number,
    _model_metrics_table,
    _plot_chart,
    _rename_for_display,
    _render_priority_queue,
    _render_risk_brief,
    _risk_brief_table,
    _select_columns,
    _threshold_watch_cards_html,
    _threshold_watch_table,
    apply_plotly_theme,
    comparison_cards_html,
    metric_card,
    render_table,
    section_header,
)
from src.dashboard.context import PageContext
from src.dashboard.maps import _render_station_map
from src.risk_brief import build_station_risk_brief, describe_anomaly_evidence
from src.station_comparison import build_station_comparison, choose_recommended_station, export_comparison_csv
from src.theme import chart_color_sequence, hex_to_rgb

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

def render(context: PageContext) -> None:
    source = context.data.source
    selected = context.data.selected
    regional = context.data.regional
    comparison_scope = context.data.comparison
    features = source.features
    filtered_features = selected.features
    filtered_predictions = selected.predictions
    filtered_anomalies = selected.anomalies
    filtered_events = selected.events
    map_features = regional.features
    map_predictions = regional.predictions
    map_anomalies = regional.anomalies
    comparison_features = comparison_scope.features
    comparison_predictions = comparison_scope.predictions
    comparison_anomalies = comparison_scope.anomalies
    predictor_metrics = context.metrics.predictor
    anomaly_metrics = context.metrics.anomaly
    backtest_metrics = context.metrics.backtest
    confidence_metrics = context.metrics.confidence
    data_health = context.metrics.data_health
    evaluation_summary = context.metrics.evaluation
    config = context.config
    theme = context.theme
    source_code = context.source_code
    data_source = context.data_source
    selected_site = context.filters.site_name
    selected_site_display = context.filters.site_display
    quality = data_quality_summary(filtered_features)
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
