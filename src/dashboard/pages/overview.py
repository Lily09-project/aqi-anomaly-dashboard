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
    if filtered_features.empty:
        st.info("目前篩選條件下沒有 AQI 資料。")
        return
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
