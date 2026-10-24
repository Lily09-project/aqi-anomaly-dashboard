"""Chinese display names for counties and stations, shared by the pipeline."""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.station_registry import get_station_location as registry_get_station_location


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


def get_station_location(site_name: Any, county_display: Any = None) -> dict[str, Any] | None:
    """Return a station location together with coordinate provenance."""
    site = to_chinese_site_name(site_name)
    county = to_chinese_location_name(county_display)
    return registry_get_station_location(site, county)


def get_station_coordinates(site_name: Any, county_display: Any = None) -> tuple[float, float] | None:
    """Return coordinates while preserving the legacy tuple interface."""
    location = get_station_location(site_name, county_display)
    if not location or location.get("latitude") is None or location.get("longitude") is None:
        return None
    return float(location["latitude"]), float(location["longitude"])


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
