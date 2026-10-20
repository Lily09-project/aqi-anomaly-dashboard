"""Build a minimal, allowlisted static release; never publish the repository root."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ASSETS = ("index.html", "styles.css", "app.js")
OUTPUT_FILES = frozenset((*ASSETS, "data.json", "integrity.json", ".nojekyll"))
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 20000


def safe_path(root: Path, relative: str) -> Path:
    candidate = root / relative
    resolved_root = root.resolve()
    candidate.resolve().relative_to(resolved_root)
    if any(path.is_symlink() for path in (candidate, *candidate.parents) if path != resolved_root.parent):
        raise ValueError("Symlinks are not valid public inputs")
    if not candidate.is_file() or candidate.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Missing or oversized public input: " + relative)
    return candidate


def number(value: str | None) -> float | None:
    if value is None or value.strip().lower() in {"", "nan", "none", "null"}:
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Non-finite public number")
    return result


def read_rows(root: Path, path: str, columns: list[tuple[str, str, str]]) -> list[dict]:
    source = safe_path(root, path)
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {key for key, _, _ in columns}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Missing required public columns: " + path)
        rows = []
        for raw in reader:
            if len(rows) >= MAX_ROWS:
                raise ValueError("Public row limit exceeded")
            row = {}
            for key, _, kind in columns:
                value = raw.get(key)
                if kind == "number":
                    row[key] = number(value)
                else:
                    text = str(value or "").strip()
                    if len(text) > 500:
                        raise ValueError("Oversized public cell")
                    if kind == "date" and text:
                        datetime.fromisoformat(text)
                    row[key] = text or None
            rows.append(row)
    if not rows:
        raise ValueError("Empty public dataset: " + path)
    return rows


def dataset(root: Path, key: str, label: str, path: str, columns: list[tuple[str, str, str]],
            *, identity: list[str], group: str, group_label: str, value: str, date: str | None,
            chart_label: str, sort: str | None = None, name: str | None = None,
            secondary: str | None = None, minimum: dict | None = None) -> dict:
    rows = read_rows(root, path, columns)
    ids = [json.dumps([row[column] for column in identity], ensure_ascii=False) for row in rows]
    if any(any(row[column] is None for column in identity) for row in rows) or len(ids) != len(set(ids)):
        raise ValueError("Missing or duplicate public identity: " + key)
    return {"id": key, "label": label, "fields": [{"key": k, "label": title, "kind": kind} for k, title, kind in columns],
            "identity": identity, "group": group, "groupLabel": group_label, "value": value,
            "date": date, "chartLabel": chart_label, "sort": sort or date or value,
            "name": name or identity[-1], "secondary": secondary, "minimum": minimum, "rows": rows}


def read_json(root: Path, path: str) -> dict:
    value = json.loads(safe_path(root, path).read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Public metadata must be an object")
    return value


def metric_dataset(root: Path, path: str, keys: tuple[str, ...], group_key: str | None = None) -> dict:
    payload = read_json(root, path)
    rows = []
    if group_key:
        payload = payload[group_key]
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
            rows.append({"model": "預先計算結果", "metric": key.upper(), "value": float(value)})
    if not rows:
        raise ValueError("Missing public evaluation metrics")
    return {"id": "metrics", "label": "模型評估", "fields": [
        {"key": "model", "label": "模型", "kind": "text"},
        {"key": "metric", "label": "指標", "kind": "text"},
        {"key": "value", "label": "指標值", "kind": "number"}],
        "identity": ["metric"], "group": "model", "groupLabel": "模型", "value": "value",
        "date": None, "chartLabel": "評估結果（各指標單位不同，請以明細解讀）", "sort": "metric",
        "name": "metric", "secondary": None, "minimum": None, "rows": rows}


def validate_payload(payload: dict) -> None:
    if payload["schema_version"] != "pages-data/1" or not payload["datasets"]:
        raise ValueError("Invalid public schema")
    for item in payload["datasets"]:
        keys = {field["key"] for field in item["fields"]}
        if not {item["group"], item["value"], *item["identity"]}.issubset(keys):
            raise ValueError("Dataset configuration references unpublished columns")
        if item["date"] and item["date"] not in keys:
            raise ValueError("Missing public date")
        for row in item["rows"]:
            if set(row) != keys:
                raise ValueError("Row violates public column allowlist")
    json.dumps(payload, allow_nan=False)


def write_release(root: Path, payload: dict) -> Path:
    validate_payload(payload)
    destination = root / "pages-dist"
    if destination.is_symlink():
        raise ValueError("Invalid output symlink")
    destination.mkdir(exist_ok=True)
    if any(path.name not in OUTPUT_FILES or path.is_symlink() or not path.is_file() for path in destination.iterdir()):
        raise ValueError("Unexpected output inventory; refusing to publish")
    for name in ASSETS:
        shutil.copyfile(safe_path(root, "web/" + name), destination / name)
    content = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("Public bundle too large")
    (destination / "data.json").write_text(content, encoding="utf-8", newline="\n")
    integrity = {"schema_version": "pages-integrity/1",
                 "data_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                 "files": list((*ASSETS, "data.json", ".nojekyll"))}
    (destination / "integrity.json").write_text(json.dumps(integrity, indent=2) + "\n", encoding="utf-8")
    (destination / ".nojekyll").write_text("", encoding="utf-8")
    if {path.name for path in destination.iterdir()} != OUTPUT_FILES:
        raise ValueError("Incomplete public output")
    return destination


def build_payload(root: Path) -> dict:
    basic = [("datetime", "時間", "date"), ("county", "縣市", "text"), ("site_name", "測站", "text"),
             ("aqi", "AQI", "number"), ("pm25", "PM2.5", "number")]
    views = [dataset(root, "overview", "空品總覽", "data/processed/aqi_features.csv", basic,
                     identity=["datetime", "site_name"], group="county", group_label="縣市",
                     value="aqi", date="datetime", chart_label="AQI 趨勢（同縣市測站平均）")]
    anomaly = dataset(root, "anomaly", "異常偵測", "data/processed/aqi_anomaly_results.csv",
                      basic + [("is_anomaly", "異常標記", "number"), ("anomaly_score", "異常分數", "number")],
                      identity=["datetime", "site_name"], group="site_name", group_label="測站",
                      value="aqi", date="datetime", chart_label="空品趨勢與異常明細")
    views.append(anomaly)
    forecast_columns = [("datetime", "時間", "date"), ("site_name", "測站", "text"),
                        ("actual_next_hour_aqi", "實際次小時 AQI", "number"),
                        ("predicted_next_hour_aqi", "預測次小時 AQI", "number")]
    views.append(dataset(root, "forecast", "預測驗證", "data/processed/aqi_predictions.csv", forecast_columns,
                         identity=["datetime", "site_name"], group="site_name", group_label="測站",
                         value="predicted_next_hour_aqi", secondary="actual_next_hour_aqi", date="datetime",
                         chart_label="歷史留出集：預測與實際 AQI"))
    latest = {}
    for row in views[0]["rows"]:
        if row["site_name"] not in latest or row["datetime"] > latest[row["site_name"]]["datetime"]:
            latest[row["site_name"]] = row
    comparison = {**views[0], "id": "stations", "label": "測站比較", "rows": list(latest.values()),
                  "identity": ["site_name"], "date": None, "name": "site_name", "sort": "aqi",
                  "chartLabel": "各站最新示範 AQI"}
    views.append(comparison)
    views.append(metric_dataset(root, "reports/metrics/predictor_metrics.json", ("mae", "rmse", "r2")))
    dates = [row["datetime"][:10] for row in views[0]["rows"]]
    return {"schema_version": "pages-data/1", "kind": "aqi", "project": "aqi-anomaly-dashboard",
            "title": "空氣品質觀測室", "brand": "AIR QUALITY DESK",
            "source": {"mode": "DEMO · 示範資料", "range": min(dates) + "–" + max(dates), "captured_at": None},
            "notice": "以合成資料展示空品分析與模型驗證，非即時監測或未來預報。",
            "disclaimer": "僅供技術展示；實際空品與活動安排請查詢環境部官方資訊。",
            "quality": {"資料來源": "固定亂數種子生成的合成資料", "觀測筆數": len(views[0]["rows"]),
                        "模型評估": "歷史留出集 MAE／RMSE／R²", "執行方式": "發布前計算；瀏覽器不執行模型",
                        "下載範圍": "目前篩選結果；比較報告僅包含選取資料"},
            "datasets": views}

def build(root: Path = ROOT) -> Path:
    return write_release(root, build_payload(root))


if __name__ == "__main__":
    print("Built verified static release:", build())
