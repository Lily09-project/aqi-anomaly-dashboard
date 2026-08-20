import pandas as pd

from src.app_helpers import data_quality_summary
from src.dashboard.components import DISPLAY_COLUMN_MAP, _rename_for_display, _select_columns, metric_card, render_table
from src.dashboard.context import PageContext
from src.dashboard.provenance import source_status_panel

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None


def render(context: PageContext) -> None:
    selected = context.data.selected
    filtered_features = selected.features
    data_health = context.metrics.data_health
    source_metadata = context.metrics.source_metadata
    data_source = context.data_source
    quality = data_quality_summary(filtered_features)

    st.markdown(
        '<div class="section-note">此頁整理資料完整性、缺失值與來源摘要，協助快速判斷目前資料是否適合分析。</div>',
        unsafe_allow_html=True,
    )
    source_status_panel(source_metadata)

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

    freshness_cols = st.columns(4, gap="large")
    freshness_cols[0].metric("來源狀態", data_health.get("source_status", "未知"))
    freshness_cols[1].metric("資料提供者", data_health.get("provider", "未知"))
    freshness_cols[2].metric("取得時間", str(data_health.get("fetched_at_utc") or "未知"))
    observation_delay = data_health.get("observation_delay_hours")
    freshness_cols[3].metric("觀測延遲", "N/A" if observation_delay is None else f"{float(observation_delay):g} 小時")
    if data_health.get("fallback_reason"):
        st.warning(f"Fallback 原因：{data_health['fallback_reason']}")

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