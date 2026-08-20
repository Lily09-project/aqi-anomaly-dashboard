from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Mapping

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None


_FALLBACK_REASON_LABELS = {
    "api_url_not_configured": "尚未設定 API URL",
    "requests_not_installed": "缺少 requests 套件",
    "api_request_failed": "API 請求失敗或逾時",
    "required_columns_missing": "API 欄位不完整",
}


def _format_timestamp(value: object) -> str:
    if value in {None, "", "未知"}:
        return "未知"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%Y/%m/%d %H:%M UTC")
    except (TypeError, ValueError):
        return str(value)


def format_source_status(source_metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    """Convert provenance metadata into a small, presentation-safe status contract."""
    source = source_metadata if isinstance(source_metadata, Mapping) else {}
    status = str(source.get("status", "unknown"))
    data_source = str(source.get("data_source", "Unknown"))
    source_is_stale = bool(source.get("source_is_stale"))
    observation_is_stale = bool(source.get("observation_is_stale"))
    fallback_reason = source.get("fallback_reason")
    provider = str(source.get("provider", "unknown"))
    fetched_at = _format_timestamp(source.get("fetched_at_utc"))
    latest_observation = _format_timestamp(
        source.get("latest_observation")
        or (source.get("datetime_range", {}) or {}).get("max")
        if isinstance(source.get("datetime_range", {}), Mapping)
        else None
    )

    if status == "success" and data_source == "API Data" and not (source_is_stale or observation_is_stale):
        return {
            "label": "API Data · 已更新",
            "tone": "positive",
            "detail": f"{provider} · 取得 {fetched_at} · 最新觀測 {latest_observation}",
            "is_warning": False,
            "data_source": data_source,
            "provider": provider,
            "fetched_at": fetched_at,
            "latest_observation": latest_observation,
            "fallback_reason": "",
        }
    if status == "success" and data_source == "API Data":
        stale_reason = "來源取得時間較舊" if source_is_stale else "最新觀測時間較舊"
        return {
            "label": f"API Data · {stale_reason}",
            "tone": "warning",
            "detail": f"{provider} · 取得 {fetched_at} · 最新觀測 {latest_observation}",
            "is_warning": True,
            "data_source": data_source,
            "provider": provider,
            "fetched_at": fetched_at,
            "latest_observation": latest_observation,
            "fallback_reason": "",
        }
    if status == "fallback" or data_source == "Sample Data":
        reason = _FALLBACK_REASON_LABELS.get(str(fallback_reason), str(fallback_reason or "本次執行使用模擬資料"))
        label = "Sample Data · API fallback" if status == "fallback" else "Sample Data · 模擬資料"
        return {
            "label": label,
            "tone": "warning",
            "detail": f"{reason} · 不代表官方即時觀測",
            "is_warning": True,
            "data_source": "Sample Data",
            "provider": provider,
            "fetched_at": fetched_at,
            "latest_observation": latest_observation,
            "fallback_reason": reason,
        }
    return {
        "label": "來源未知 · 需重新產生資料",
        "tone": "warning",
        "detail": "找不到有效 provenance metadata，不能確認資料是否新鮮或來自 API。",
        "is_warning": True,
        "data_source": data_source,
        "provider": provider,
        "fetched_at": fetched_at,
        "latest_observation": latest_observation,
        "fallback_reason": "metadata_missing_or_invalid",
    }


def source_status_panel(source_metadata: Mapping[str, Any] | None, st_api: Any = None) -> dict[str, Any]:
    """Render a compact provenance panel without exposing raw JSON."""
    api = st_api if st_api is not None else st
    status = format_source_status(source_metadata)
    if api is None:
        return status
    api.markdown(
        f"""
        <section class="source-status-panel {escape(str(status['tone']))}" aria-label="資料來源狀態">
            <div class="source-status-head">
                <span class="source-status-kicker">資料來源狀態</span>
                <strong>{escape(str(status['label']))}</strong>
            </div>
            <p>{escape(str(status['detail']))}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    return status
