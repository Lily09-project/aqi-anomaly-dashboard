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
