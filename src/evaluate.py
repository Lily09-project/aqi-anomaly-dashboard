from __future__ import annotations

import argparse
import base64
import json
import struct
import zlib

import pandas as pd

from src.data_health import build_data_health
from src.monitoring import build_monitoring_report
from src.monitoring_history import build_monitoring_snapshot, update_monitoring_history
from src.source_metadata import load_source_metadata
from src.theme import THEME
from src.utils import ensure_parent, load_config, resolve_path, write_json


_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def _write_placeholder_png(path) -> None:
    p = ensure_parent(path)
    with p.open("wb") as f:
        f.write(_TINY_PNG)


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))


def _save_rgb_png(path, pixels: list[list[tuple[int, int, int]]]) -> None:
    height = len(pixels)
    width = len(pixels[0])
    raw = b"".join(b"\x00" + b"".join(bytes(px) for px in row) for row in pixels)
    payload = zlib.compress(raw, 9)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", payload)
    png += chunk(b"IEND", b"")
    p = ensure_parent(path)
    with p.open("wb") as f:
        f.write(png)


def _draw_line(canvas, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
    height = len(canvas)
    width = len(canvas[0])
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        if 0 <= x0 < width and 0 <= y0 < height:
            canvas[y0][x0] = color
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _draw_point(canvas, x: int, y: int, color: tuple[int, int, int], radius: int = 2) -> None:
    height = len(canvas)
    width = len(canvas[0])
    for yy in range(y - radius, y + radius + 1):
        for xx in range(x - radius, x + radius + 1):
            if (xx - x) ** 2 + (yy - y) ** 2 <= radius**2 and 0 <= xx < width and 0 <= yy < height:
                canvas[yy][xx] = color


def _scale(values: pd.Series, lo: int, hi: int, invert: bool = False) -> list[int]:
    vals = pd.to_numeric(values, errors="coerce").fillna(0)
    min_v = float(vals.min())
    max_v = float(vals.max())
    if max_v == min_v:
        return [int((lo + hi) / 2)] * len(vals)
    scaled = lo + (vals - min_v) * (hi - lo) / (max_v - min_v)
    if invert:
        scaled = hi - (scaled - lo)
    return scaled.astype(int).tolist()


def _fallback_chart(points: pd.DataFrame, x_col: str | None, y_col: str, path, scatter: bool = False, color_col: str | None = None) -> None:
    width, height = 960, 420
    bg = _hex_to_rgb(THEME["surface"])
    axis = _hex_to_rgb(THEME["text"])
    grid = _hex_to_rgb(THEME["pale_blue"])
    blue = _hex_to_rgb(THEME["primary"])
    soft = _hex_to_rgb(THEME["light_blue"])
    coral = _hex_to_rgb(THEME["accent"])
    canvas = [[bg for _ in range(width)] for _ in range(height)]
    left, top, right, bottom = 58, 28, width - 24, height - 46

    for y in range(top, bottom + 1, 62):
        _draw_line(canvas, left, y, right, y, grid)
    _draw_line(canvas, left, top, left, bottom, axis)
    _draw_line(canvas, left, bottom, right, bottom, axis)

    if points.empty:
        _save_rgb_png(path, canvas)
        return

    if x_col:
        xs = _scale(points[x_col], left, right)
    else:
        xs = [left + int(i * (right - left) / max(1, len(points) - 1)) for i in range(len(points))]
    ys = _scale(points[y_col], top, bottom, invert=True)

    if scatter:
        for idx, (x, y) in enumerate(zip(xs, ys)):
            if color_col and int(points.iloc[idx][color_col]) == 1:
                color = coral
                radius = 3
            else:
                color = soft
                radius = 2
            _draw_point(canvas, x, y, color, radius)
    else:
        for x0, y0, x1, y1 in zip(xs, ys, xs[1:], ys[1:]):
            _draw_line(canvas, x0, y0, x1, y1, blue)
        for x, y in zip(xs[:: max(1, len(xs) // 42)], ys[:: max(1, len(ys) // 42)]):
            _draw_point(canvas, x, y, coral, 2)

    _save_rgb_png(path, canvas)


def _plot_fallback_figures(features: pd.DataFrame, predictions: pd.DataFrame, anomalies: pd.DataFrame, figures_dir) -> None:
    sample_site = features["site_name"].iloc[0]
    trend = features[features["site_name"] == sample_site].tail(168).reset_index(drop=True)
    _fallback_chart(trend, None, "aqi", figures_dir / "aqi_trend.png")
    _fallback_chart(
        predictions.rename(columns={"actual_next_hour_aqi": "x", "predicted_next_hour_aqi": "y"}),
        "x",
        "y",
        figures_dir / "prediction_vs_actual.png",
        scatter=True,
    )
    recent = anomalies.tail(300).reset_index(drop=True)
    _fallback_chart(recent, None, "aqi", figures_dir / "anomaly_cases.png", scatter=True, color_col="is_anomaly")


def _plot_figures(features: pd.DataFrame, predictions: pd.DataFrame, anomalies: pd.DataFrame, figures_dir) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    try:
        import matplotlib.pyplot as plt  # type: ignore

        sample_site = features["site_name"].iloc[0]
        trend = features[features["site_name"] == sample_site].tail(168)
        plt.figure(figsize=(10, 4))
        plt.plot(trend["datetime"], trend["aqi"], color=THEME["primary"], linewidth=2)
        plt.title("AQI Trend")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.savefig(figures_dir / "aqi_trend.png", dpi=150)
        plt.close()

        plt.figure(figsize=(5, 5))
        plt.scatter(
            predictions["actual_next_hour_aqi"],
            predictions["predicted_next_hour_aqi"],
            s=18,
            color=THEME["normal"],
            alpha=0.75,
        )
        low = min(predictions["actual_next_hour_aqi"].min(), predictions["predicted_next_hour_aqi"].min())
        high = max(predictions["actual_next_hour_aqi"].max(), predictions["predicted_next_hour_aqi"].max())
        plt.plot([low, high], [low, high], color=THEME["accent"], linewidth=2)
        plt.xlabel("Actual next-hour AQI")
        plt.ylabel("Predicted next-hour AQI")
        plt.tight_layout()
        plt.savefig(figures_dir / "prediction_vs_actual.png", dpi=150)
        plt.close()

        recent = anomalies.tail(300)
        plt.figure(figsize=(10, 4))
        plt.scatter(recent["datetime"], recent["aqi"], c=recent["is_anomaly"], cmap="coolwarm", s=22)
        plt.title("Recent Anomaly Cases")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        plt.savefig(figures_dir / "anomaly_cases.png", dpi=150)
        plt.close()
    except Exception:
        try:
            _plot_fallback_figures(features, predictions, anomalies, figures_dir)
        except Exception:
            for name in ["aqi_trend.png", "prediction_vs_actual.png", "anomaly_cases.png"]:
                _write_placeholder_png(figures_dir / name)


def evaluate(source_metadata: dict[str, object] | None = None) -> dict[str, object]:
    config = load_config()
    features = pd.read_csv(resolve_path(config, "data.features_file"), parse_dates=["datetime"])
    predictions = pd.read_csv(resolve_path(config, "data.predictions_file"), parse_dates=["datetime"])
    monitoring_predictions_path = resolve_path(config, "data.monitoring_predictions_file")
    monitoring_predictions = (
        pd.read_csv(monitoring_predictions_path, parse_dates=["datetime", "training_cutoff"])
        if monitoring_predictions_path.exists()
        else predictions
    )
    anomalies = pd.read_csv(resolve_path(config, "data.anomaly_file"), parse_dates=["datetime"])
    events_path = resolve_path(config, "data.events_file")
    events = pd.read_csv(events_path, parse_dates=["datetime", "end_datetime", "peak_datetime"]) if events_path.exists() else pd.DataFrame()
    metrics_dir = resolve_path(config, "reports.metrics_dir")
    figures_dir = resolve_path(config, "reports.figures_dir")

    predictor_metrics_path = metrics_dir / "predictor_metrics.json"
    anomaly_metrics_path = metrics_dir / "anomaly_metrics.json"
    backtest_metrics_path = metrics_dir / "backtest_metrics.json"
    predictor_metrics = json.loads(predictor_metrics_path.read_text(encoding="utf-8")) if predictor_metrics_path.exists() else {}
    anomaly_metrics = json.loads(anomaly_metrics_path.read_text(encoding="utf-8")) if anomaly_metrics_path.exists() else {}
    backtest_metrics = json.loads(backtest_metrics_path.read_text(encoding="utf-8")) if backtest_metrics_path.exists() else {}
    confidence_path = resolve_path(config, "reports.confidence_file")
    confidence_metrics = json.loads(confidence_path.read_text(encoding="utf-8")) if confidence_path.exists() else {}
    provenance = source_metadata if source_metadata is not None else load_source_metadata(config)
    stale_after_hours = int(config.get("data", {}).get("stale_after_hours", 3))
    data_health = build_data_health(features, stale_after_hours=stale_after_hours, source_metadata=provenance)
    monitoring_config = config.get("monitoring", {})
    monitoring = build_monitoring_report(
        features,
        monitoring_predictions,
        reference_days=int(monitoring_config.get("reference_days", 14)),
        current_days=int(monitoring_config.get("current_days", 7)),
        thresholds=monitoring_config.get("thresholds", {}),
    )
    data_end = features["datetime"].max().isoformat()
    monitoring_snapshot = build_monitoring_snapshot(
        monitoring,
        data_end=data_end,
        data_source=str(provenance.get("data_source", "Unknown")),
        model_name=str(predictor_metrics.get("best_model", "unknown")),
    )
    history_path = resolve_path(config, "monitoring.history_file")
    monitoring_history = update_monitoring_history(
        history_path,
        monitoring_snapshot,
        max_entries=int(monitoring_config.get("max_history_entries", 90)),
    )

    summary = {
        "rows": {
            "features": int(len(features)),
            "predictions": int(len(predictions)),
            "anomaly_results": int(len(anomalies)),
            "anomaly_events": int(len(events)),
        },
        "site_count": int(features["site_name"].nunique()),
        "datetime_range": {
            "start": str(features["datetime"].min()),
            "end": str(features["datetime"].max()),
        },
        "predictor_metrics": predictor_metrics,
        "anomaly_metrics": anomaly_metrics,
        "backtest_metrics": backtest_metrics,
        "forecast_confidence": confidence_metrics,
        "data_health": data_health,
        "monitoring": monitoring,
        "monitoring_history": {
            "entry_count": monitoring_history["entry_count"],
            "latest_status": monitoring_snapshot["status"],
            "latest_action": monitoring_snapshot["action"],
        },
        "interpretation": [
            "Moving Average 作為下一小時 AQI 預測 baseline。",
            "預測模型僅以 validation split 選擇，final test 僅用於最終報告；rolling-origin backtest 用於檢查多個歷史時間窗。",
            "異常偵測使用 pseudo-label 評估，正式應用前應以真實污染事件標註驗證。",
            "預測區間由 final test 之前的 rolling-origin 殘差校準；final test 只用於報告 empirical coverage。",
            "本專案是本地端技術展示，不是正式環境監測系統。",
        ],
    }

    _plot_figures(features, predictions, anomalies, figures_dir)
    write_json(metrics_dir / "data_health.json", data_health)
    monitoring_path = resolve_path(config, "reports.monitoring_file") if "monitoring_file" in config.get("reports", {}) else metrics_dir / "monitoring.json"
    write_json(monitoring_path, monitoring)
    write_json(metrics_dir / "evaluation_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    summary = evaluate()
    print(f"Evaluation summary written for {summary['rows']['features']:,} feature rows")


if __name__ == "__main__":
    main()
