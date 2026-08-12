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
