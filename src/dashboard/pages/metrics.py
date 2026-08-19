import json

import pandas as pd

from src.dashboard.components import (
    _backtest_aggregate_table,
    _model_metrics_table,
    metric_card,
    render_table,
)
from src.dashboard.context import PageContext

try:
    import streamlit as st  # type: ignore
except Exception:  # pragma: no cover
    st = None

def reliability_station_table(predictor_metrics: dict[str, object]) -> pd.DataFrame:
    reliability = predictor_metrics.get("reliability", {})
    rows = reliability.get("by_station", []) if isinstance(reliability, dict) else []
    columns = ["station", "rows", "mae", "rmse", "r2"]
    return pd.DataFrame(rows).reindex(columns=columns)


def station_coverage_table(confidence_metrics: dict[str, object]) -> pd.DataFrame:
    coverage = confidence_metrics.get("station_coverage", {})
    groups = coverage.get("groups", []) if isinstance(coverage, dict) else []
    rows: list[dict[str, object]] = []
    for group in groups:
        intervals = group.get("intervals", {})
        row: dict[str, object] = {
            "station": group.get("station", "N/A"),
            "rows": group.get("rows", 0),
        }
        for level in ("80", "95"):
            values = intervals.get(level, {})
            row[f"rows_{level}"] = values.get("rows", 0)
            row[f"coverage_{level}"] = values.get("empirical_coverage", 0.0)
            row[f"mean_width_{level}"] = values.get("mean_width", 0.0)
        rows.append(row)
    return pd.DataFrame(rows)


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def manifest_evidence_table(manifest: dict[str, object]) -> pd.DataFrame:
    """Flatten the run manifest into a reviewer-readable evidence table."""
    project = _mapping(manifest.get("project"))
    run = _mapping(manifest.get("run"))
    contract = _mapping(manifest.get("data_contract"))
    config = _mapping(run.get("config"))
    requirements = _mapping(run.get("requirements"))
    artifacts = manifest.get("artifacts", [])
    artifact_records = [item for item in artifacts if isinstance(item, dict)] if isinstance(artifacts, list) else []
    complete_artifacts = sum(
        bool(item.get("exists")) and bool(item.get("sha256")) for item in artifact_records
    )

    rows = [
        {"項目": "執行時間 (UTC)", "內容": str(manifest.get("generated_at_utc", "N/A"))},
        {"項目": "Git revision", "內容": str(project.get("git_revision", "N/A"))},
        {"項目": "工作樹狀態", "內容": "乾淨" if project.get("git_dirty") is False else "需檢查"},
        {"項目": "資料模式", "內容": str(run.get("data_source", "N/A"))},
        {"項目": "預測目標", "內容": str(contract.get("target", "N/A"))},
        {"項目": "Feature contract", "內容": "通過" if contract.get("feature_contract_valid") else "需檢查"},
        {"項目": "時間切分", "內容": str(contract.get("split_strategy", "N/A"))},
        {"項目": "Artifact SHA-256", "內容": f"{complete_artifacts}/{len(artifact_records)} 已記錄"},
        {"項目": "設定檔雜湊", "內容": str(config.get("sha256", "N/A"))},
        {"項目": "依賴檔雜湊", "內容": str(requirements.get("sha256", "N/A"))},
    ]
    return pd.DataFrame(rows)


def render(context: PageContext) -> None:
    predictor_metrics = context.metrics.predictor
    anomaly_metrics = context.metrics.anomaly
    backtest_metrics = context.metrics.backtest
    confidence_metrics = context.metrics.confidence
    evaluation_summary = context.metrics.evaluation
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

    reliability = predictor_metrics.get("reliability", {})
    if isinstance(reliability, dict) and reliability:
        st.subheader("模型可靠性與弱點")
        improvement = reliability.get("baseline_improvement", {})
        worst = reliability.get("worst_station", {})
        summary_columns = st.columns(3)
        with summary_columns[0]:
            metric_card("相對移動平均 MAE 改善", f'{float(improvement.get("mae_reduction_pct", 0)):.1f}%', f'樣本 {int(improvement.get("rows", 0)):,} 筆')
        with summary_columns[1]:
            metric_card("最弱測站", worst.get("station", "N/A"), f'RMSE {float(worst.get("rmse", 0)):.2f}')
        with summary_columns[2]:
            metric_card("最弱站樣本數", int(worst.get("rows", 0)), "樣本少時僅作診斷提示")

        station_table = reliability_station_table(predictor_metrics)
        if not station_table.empty:
            render_table(
                station_table.rename(
                    columns={"station": "測站", "rows": "樣本數", "mae": "MAE", "rmse": "RMSE", "r2": "R2"}
                ),
                label="各測站 final-test 可靠性",
            )
        band_table = pd.DataFrame(reliability.get("by_aqi_band", []))
        if not band_table.empty:
            render_table(
                band_table.rename(
                    columns={"aqi_band": "實際 AQI 區間", "rows": "樣本數", "mae": "MAE", "rmse": "RMSE", "r2": "R2"}
                ),
                label="各 AQI 區間可靠性",
            )
        st.caption("分組指標皆顯示樣本數；小樣本測站或高 AQI 區間的數值波動較大，不應單獨作為部署依據。")

    coverage_table = station_coverage_table(confidence_metrics)
    if not coverage_table.empty:
        st.subheader("分測站預測區間覆蓋率")
        render_table(
            coverage_table.rename(
                columns={
                    "station": "測站",
                    "rows": "實際值樣本數",
                    "rows_80": "80% 有效樣本",
                    "coverage_80": "80% 覆蓋率",
                    "mean_width_80": "80% 平均寬度",
                    "rows_95": "95% 有效樣本",
                    "coverage_95": "95% 覆蓋率",
                    "mean_width_95": "95% 平均寬度",
                }
            ),
            label="各測站 final-test 區間校準檢查",
        )
        st.caption("區間由 final test 之前的 rolling-origin 殘差校準；此表只評估覆蓋率，不用測試結果回頭調整寬度。")
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

    st.subheader("審查證據與可重現性")
    manifest = context.metrics.manifest
    if not manifest:
        st.info("目前找不到 run manifest；請重新執行 sample pipeline 以建立可追溯執行證據。")
    else:
        project = _mapping(manifest.get("project"))
        run = _mapping(manifest.get("run"))
        artifacts = manifest.get("artifacts", [])
        artifact_records = [item for item in artifacts if isinstance(item, dict)] if isinstance(artifacts, list) else []
        complete_artifacts = sum(
            bool(item.get("exists")) and bool(item.get("sha256")) for item in artifact_records
        )
        revision = str(project.get("git_revision", "N/A"))
        st.caption("此區塊將一次 pipeline 的版本、資料 contract 與輸出雜湊轉成可供審查的摘要，不顯示 raw JSON。")
        evidence_columns = st.columns(3)
        evidence_columns[0].metric("Git revision", revision[:12] if revision else "N/A")
        evidence_columns[1].metric("輸出完整度", f"{complete_artifacts}/{len(artifact_records)}")
        evidence_columns[2].metric("資料模式", str(run.get("data_source", "N/A")))
        render_table(manifest_evidence_table(manifest), label="執行證據摘要")
        limitations = manifest.get("limitations", [])
        if isinstance(limitations, list) and limitations:
            st.caption("限制：" + "；".join(str(item) for item in limitations))
        run_id = str(manifest.get("run_id", "run"))
        st.download_button(
            "下載完整 run manifest (.json)",
            data=json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"taiwan_aqi_run_manifest_{run_id}.json",
            mime="application/json",
            use_container_width=True,
            key="metrics_manifest_download",
        )

    st.markdown(
        '<div class="section-note">限制：Sample Data 是模擬資料；API 欄位格式可能變動；異常偵測目前沒有人工標註 ground truth。未來可接入排程 API、真實事件標註與更嚴格的時間序列交叉驗證。</div>',
        unsafe_allow_html=True,
    )
