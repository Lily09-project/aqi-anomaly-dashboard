from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd

from src.dashboard.styles import inject_global_css as _inject_global_css
from src.dashboard.components import (
    DISPLAY_COLUMN_MAP,
    METRIC_DISPLAY_COLUMNS,
    MODEL_DISPLAY_NAMES,
    _backtest_aggregate_table,
    _confidence_summary_table,
    _display_source,
    _format_optional_number,
    _format_value,
    _model_metrics_table,
    _plot_chart,
    _rename_for_display,
    _render_priority_queue,
    _render_risk_brief,
    _risk_brief_table,
    _safe_date_range,
    _select_columns,
    _site_lookup,
    _source_caption,
    _threshold_watch_cards_html,
    _threshold_watch_table,
    activity_guidance_panel,
    apply_plotly_theme,
    comparison_cards_html,
    metric_card,
    render_table,
    section_header,
    signal_deck,
)
from src.dashboard.maps import _build_station_map, _render_station_map, _station_map_data
from src.dashboard.context import FilterState, PageContext
from src.dashboard.data_service import build_filtered_data, load_dashboard_artifacts
from src.dashboard.navigation import VIEW_LABELS, render_active_view
from src.dashboard.pages import (
    PAGE_RENDERERS,
    render_anomaly,
    render_comparison,
    render_metrics,
    render_overview,
    render_prediction,
    render_quality,
)
from src.consumer_brief import (
    aqi_guidance,
    build_consumer_summary,
    build_reliability_report,
    export_csv_bytes,
    export_reliability_report_bytes,
    format_observation_status,
)
from src.app_helpers import (
    aqi_category,
    compute_kpis,
    data_quality_summary,
    get_station_coordinates,
    infer_data_source,
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


def inject_global_css(theme: dict[str, str] | None = None) -> None:
    _inject_global_css(st, theme)


def inject_theme(theme: dict[str, str] | None = None) -> None:
    inject_global_css(theme)


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

    source_data, dashboard_metrics = load_dashboard_artifacts(config)
    features = source_data.features
    predictions = source_data.predictions
    anomalies = source_data.anomalies
    events = source_data.events
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
    filter_state = FilterState(
        county=county_filter,
        site_name=selected_site,
        site_display=selected_site_display,
        start_date=start_date,
        end_date=end_date,
    )
    filtered_data = build_filtered_data(source_data, filter_state)
    filtered_features = filtered_data.selected.features
    filtered_predictions = filtered_data.selected.predictions
    filtered_anomalies = filtered_data.selected.anomalies
    filtered_events = filtered_data.selected.events
    map_features = filtered_data.regional.features
    map_predictions = filtered_data.regional.predictions
    map_anomalies = filtered_data.regional.anomalies
    comparison_features = filtered_data.comparison.features
    comparison_predictions = filtered_data.comparison.predictions
    comparison_anomalies = filtered_data.comparison.anomalies
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
    reliability_risk_brief = build_station_risk_brief(
        filtered_features,
        reference_features=features,
        predictions=filtered_predictions,
        anomalies=filtered_anomalies,
    )
    reliability_report = build_reliability_report(
        features=filtered_features,
        predictions=filtered_predictions,
        anomalies=filtered_anomalies,
        risk_brief=reliability_risk_brief,
        predictor_metrics=dashboard_metrics.predictor,
        anomaly_metrics=dashboard_metrics.anomaly,
        confidence_metrics=dashboard_metrics.confidence,
        data_health=dashboard_metrics.data_health,
        data_source=data_source,
        selection_label=selection_label,
        filter_metadata={
            "county": selected_county,
            "station": selected_site_display,
            "start_date": str(start_date) if start_date is not None else None,
            "end_date": str(end_date) if end_date is not None else None,
        },
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
            st.download_button(
                "下載可靠性摘要 (.json)",
                data=export_reliability_report_bytes(reliability_report),
                file_name=f"taiwan_aqi_reliability_{download_date}.json",
                mime="application/json",
                use_container_width=True,
                disabled=filtered_features.empty,
            )
            st.caption("可靠性摘要整合資料品質、測站優先級、模型 metrics、預測區間與異常偵測限制；不含模型內部特徵。")
    kpis = compute_kpis(filtered_features, filtered_anomalies)
    category, _category_color = aqi_category(float(kpis["latest_aqi"]))
    predictor_metrics = dashboard_metrics.predictor
    anomaly_metrics = dashboard_metrics.anomaly
    backtest_metrics = dashboard_metrics.backtest
    confidence_metrics = dashboard_metrics.confidence
    data_health = dashboard_metrics.data_health
    evaluation_summary = dashboard_metrics.evaluation
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

    page_context = PageContext(
        data=filtered_data,
        metrics=dashboard_metrics,
        filters=filter_state,
        theme=theme,
        config=config,
        source_code=source_code,
        data_source=data_source,
    )
    selected_view = st.segmented_control(
        "Dashboard view",
        options=VIEW_LABELS,
        default=VIEW_LABELS[0],
        label_visibility="collapsed",
        key="dashboard_view",
    )
    render_active_view(selected_view or VIEW_LABELS[0], page_context, PAGE_RENDERERS)
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
