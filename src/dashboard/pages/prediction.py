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
