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
