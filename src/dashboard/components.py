from __future__ import annotations

from html import escape
from typing import Any

import pandas as pd

from src.consumer_brief import aqi_guidance, format_observation_status
from src.risk_brief import select_risk_brief_columns

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

model_metrics_table = _model_metrics_table

