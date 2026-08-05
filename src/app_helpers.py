from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.theme import THEME
from src.utils import load_config, resolve_path


COUNTY_DISPLAY_MAP = {
    "Taipei": "臺北市",
    "Taipei City": "臺北市",
    "New Taipei": "新北市",
    "New Taipei City": "新北市",
    "Taoyuan": "桃園市",
    "Taoyuan City": "桃園市",
    "Taichung": "臺中市",
    "Taichung City": "臺中市",
    "Tainan": "臺南市",
    "Tainan City": "臺南市",
    "Kaohsiung": "高雄市",
    "Kaohsiung City": "高雄市",
    "Keelung": "基隆市",
    "Hsinchu": "新竹市",
    "Hsinchu City": "新竹市",
    "Hsinchu County": "新竹縣",
    "Miaoli": "苗栗縣",
    "Changhua": "彰化縣",
    "Nantou": "南投縣",
    "Yunlin": "雲林縣",
    "Chiayi": "嘉義市",
    "Chiayi City": "嘉義市",
    "Chiayi County": "嘉義縣",
    "Pingtung": "屏東縣",
    "Yilan": "宜蘭縣",
    "Hualien": "花蓮縣",
    "Hualien County": "花蓮縣",
    "Taitung": "臺東縣",
    "Taitung County": "臺東縣",
    "Penghu": "澎湖縣",
    "Kinmen": "金門縣",
    "Lienchiang": "連江縣",
}

SITE_DISPLAY_MAP = {
    "Taipei": "松山測站",
    "Taipei City": "松山測站",
    "New Taipei": "板橋測站",
    "New Taipei City": "板橋測站",
    "Taoyuan": "桃園測站",
    "Taoyuan City": "桃園測站",
    "Taichung": "西屯測站",
    "Taichung City": "西屯測站",
    "Tainan": "安南測站",
    "Tainan City": "安南測站",
    "Kaohsiung": "前金測站",
    "Kaohsiung City": "前金測站",
    "Yilan": "宜蘭測站",
    "Hualien": "花蓮測站",
    "Hualien County": "花蓮測站",
}


# Approximate station locations for the built-in sample sites. County centroids
# provide a usable fallback for API sites that have not supplied coordinates.
STATION_COORDINATES = {
    "松山測站": (25.050, 121.548),
    "板橋測站": (25.012, 121.458),
    "桃園測站": (25.031, 121.302),
    "西屯測站": (24.181, 120.646),
    "安南測站": (23.048, 120.217),
    "前金測站": (22.627, 120.294),
    "宜蘭測站": (24.757, 121.754),
    "花蓮測站": (23.991, 121.611),
}

COUNTY_CENTROIDS = {
    "臺北市": (25.033, 121.565),
    "新北市": (25.017, 121.462),
    "桃園市": (24.993, 121.301),
    "臺中市": (24.147, 120.673),
    "臺南市": (22.999, 120.227),
    "高雄市": (22.627, 120.301),
    "基隆市": (25.128, 121.739),
    "新竹市": (24.803, 120.969),
    "新竹縣": (24.839, 121.017),
    "苗栗縣": (24.560, 120.821),
    "彰化縣": (24.076, 120.544),
    "南投縣": (23.961, 120.972),
    "雲林縣": (23.710, 120.431),
    "嘉義市": (23.480, 120.449),
    "嘉義縣": (23.452, 120.255),
    "屏東縣": (22.551, 120.549),
    "宜蘭縣": (24.757, 121.754),
    "花蓮縣": (23.991, 121.611),
    "臺東縣": (22.755, 121.150),
    "澎湖縣": (23.571, 119.579),
    "金門縣": (24.432, 118.317),
    "連江縣": (26.160, 119.951),
}


AQI_LEVELS = [
    (50, "良好", THEME["secondary"]),
    (100, "普通", THEME["light_blue"]),
    (150, "對敏感族群不健康", THEME["warning"]),
    (200, "不健康", THEME["accent"]),
    (300, "非常不健康", THEME["text"]),
]


def _clean_display_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null"} else text


def to_chinese_location_name(value: Any) -> str:
    text = _clean_display_value(value)
    if not text:
        return "未知地區"
    return COUNTY_DISPLAY_MAP.get(text, text)


def to_chinese_site_name(value: Any) -> str:
    text = _clean_display_value(value)
    if not text:
        return "未知測站"
    return SITE_DISPLAY_MAP.get(text, text)


def get_station_coordinates(site_name: Any, county_display: Any = None) -> tuple[float, float] | None:
    """Return station coordinates, then fall back to an available county centroid."""
    site = to_chinese_site_name(site_name)
    if site in STATION_COORDINATES:
        return STATION_COORDINATES[site]
    county = to_chinese_location_name(county_display)
    return COUNTY_CENTROIDS.get(county)


def add_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        if "county_display" not in out.columns:
            out["county_display"] = pd.Series(dtype="object")
        if "site_name_display" not in out.columns:
            out["site_name_display"] = pd.Series(dtype="object")
        return out
    if "county_display" not in out.columns:
        source = out["county"] if "county" in out.columns else pd.Series([""] * len(out), index=out.index)
        out["county_display"] = source.map(to_chinese_location_name)
    else:
        out["county_display"] = out["county_display"].map(to_chinese_location_name)
    if "site_name_display" not in out.columns:
        source = out["site_name"] if "site_name" in out.columns else pd.Series([""] * len(out), index=out.index)
        out["site_name_display"] = source.map(to_chinese_site_name)
    else:
        out["site_name_display"] = out["site_name_display"].map(to_chinese_site_name)
    return out


def safe_load_csv(path: str | Path, parse_dates: list[str] | None = None) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, parse_dates=parse_dates)
    except Exception:
        return pd.DataFrame()


def safe_load_json(path: str | Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return default or {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default or {}


def read_csv_or_empty(path: str | Path, parse_dates: list[str] | None = None) -> pd.DataFrame:
    return safe_load_csv(path, parse_dates=parse_dates)


def load_metrics(path: str | Path) -> dict[str, Any]:
    return safe_load_json(path)


def get_available_sites(df: pd.DataFrame) -> list[str]:
    if df.empty or "site_name" not in df.columns:
        return []
    return sorted(df["site_name"].dropna().astype(str).unique().tolist())


def load_dashboard_data(config: dict[str, Any] | None = None) -> dict[str, pd.DataFrame]:
    cfg = config or load_config()
    return {
        "features": add_display_columns(safe_load_csv(resolve_path(cfg, "data.features_file"), ["datetime"])),
        "predictions": add_display_columns(safe_load_csv(resolve_path(cfg, "data.predictions_file"), ["datetime"])),
        "anomalies": add_display_columns(safe_load_csv(resolve_path(cfg, "data.anomaly_file"), ["datetime"])),
        "events": add_display_columns(safe_load_csv(resolve_path(cfg, "data.events_file"), ["datetime", "end_datetime", "peak_datetime"])),
    }


def aqi_category(value: float) -> tuple[str, str]:
    for threshold, label, color in AQI_LEVELS:
        if value <= threshold:
            return label, color
    return "危害", THEME["text"]


def filter_by_site_and_date(
    df: pd.DataFrame,
    site_name: str | None = None,
    start_datetime: Any | None = None,
    end_datetime: Any | None = None,
    site: str | None = None,
    date_range: tuple | None = None,
    county_display: str | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if county_display and county_display != "全部縣市" and "county_display" in out:
        out = out[out["county_display"] == county_display]
    selected_site = site_name or site
    if selected_site and selected_site not in {"All", "全部測站"} and "site_name" in out:
        if selected_site in set(out["site_name"].astype(str)):
            out = out[out["site_name"].astype(str) == selected_site]
        elif "site_name_display" in out:
            out = out[out["site_name_display"].astype(str) == selected_site]
    if date_range and len(date_range) == 2:
        start_datetime, end_datetime = date_range
    if start_datetime is not None and end_datetime is not None and "datetime" in out:
        start, end = pd.to_datetime(start_datetime), pd.to_datetime(end_datetime)
        out = out[(out["datetime"] >= start) & (out["datetime"] < end + pd.Timedelta(days=1))]
    return out


def compute_kpis(features: pd.DataFrame, anomalies: pd.DataFrame) -> dict[str, float | int | str]:
    if features.empty:
        return {"latest_aqi": 0, "avg_aqi": 0, "latest_pm25": 0, "anomaly_count": 0, "category": "無資料"}
    latest_time = features["datetime"].max()
    latest_rows = features[features["datetime"] == latest_time]
    latest_aqi = float(latest_rows["aqi"].mean())
    latest_pm25 = float(latest_rows["pm25"].mean())
    category, _ = aqi_category(latest_aqi)
    return {
        "latest_aqi": round(latest_aqi, 1),
        "avg_aqi": round(float(features["aqi"].mean()), 1),
        "latest_pm25": round(latest_pm25, 1),
        "anomaly_count": int(anomalies["is_anomaly"].sum()) if not anomalies.empty and "is_anomaly" in anomalies else 0,
        "category": category,
    }


def data_quality_summary(df: pd.DataFrame) -> dict[str, int | float | str]:
    if df.empty:
        return {"rows": 0, "missing_cells": 0, "site_count": 0, "date_range": "無資料"}
    date_range = "無時間欄位"
    if "datetime" in df:
        dates = pd.to_datetime(df["datetime"], errors="coerce")
        if dates.notna().any():
            date_range = f"{dates.min():%Y/%m/%d} - {dates.max():%Y/%m/%d}"
    return {
        "rows": int(len(df)),
        "missing_cells": int(df.isna().sum().sum()),
        "site_count": int(df["site_name_display"].nunique()) if "site_name_display" in df else int(df["site_name"].nunique()) if "site_name" in df else 0,
        "date_range": date_range,
    }


def infer_data_source(config: dict[str, Any], features: pd.DataFrame | None = None) -> str:
    if features is not None and not features.empty and "data_source" in features:
        sources = features["data_source"].dropna().astype(str)
        if not sources.empty:
            return "API Data" if (sources == "API Data").any() else "Sample Data"
    raw_dir = Path(resolve_path(config, "data.raw_dir"))
    has_raw_csv = raw_dir.exists() and any(raw_dir.glob("*.csv"))
    return "API Data" if has_raw_csv and not bool(config.get("sample_mode", True)) else "Sample Data"
