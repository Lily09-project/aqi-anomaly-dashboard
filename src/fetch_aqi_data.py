from __future__ import annotations

import argparse
import os
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils import ensure_parent, load_config, project_path


ALIASES = {
    "site_name": ["site_name", "sitename", "site", "SiteName", "station", "測站", "測站名稱"],
    "county": ["county", "County", "city", "縣市"],
    "aqi": ["aqi", "AQI"],
    "pm25": ["pm2.5", "pm25", "PM2.5", "PM2.5_AVG", "pm2_5"],
    "pm10": ["pm10", "PM10"],
    "o3": ["o3", "O3"],
    "co": ["co", "CO"],
    "wind_speed": ["wind_speed", "WindSpeed", "windspeed"],
    "wind_directions": ["wind_directions", "WindDirec", "winddirec"],
    "datetime": ["datetime", "publishtime", "monitordate", "datacreationdate", "DataCreationDate", "發布時間"],
}

API_REQUIRED_COLUMNS = set(ALIASES)


def _rename_aliases(df: pd.DataFrame) -> pd.DataFrame:
    rename_map: dict[str, str] = {}
    lower_lookup = {str(c).lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            key = alias.lower().replace(" ", "").replace("_", "")
            source = lower_lookup.get(key)
            if source is not None:
                rename_map[source] = canonical
                break
    return df.rename(columns=rename_map)


def _records_to_frame(payload: Any) -> pd.DataFrame:
    if isinstance(payload, dict):
        for key in ("records", "result", "data"):
            if key in payload:
                return _records_to_frame(payload[key])
        for value in payload.values():
            if isinstance(value, list):
                return pd.DataFrame(value)
            if isinstance(value, dict):
                try:
                    return _records_to_frame(value)
                except ValueError:
                    pass
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    raise ValueError("Unsupported API response format")


def fetch_aqi_data(output_path: str | Path | None = None) -> Path | None:
    config = load_config()
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        pass

    url = str(config["api"].get("url") or os.getenv("AQI_API_URL") or "").strip()
    if not url:
        print("未設定 API URL，將使用 sample mode。")
        return None

    try:
        import requests  # type: ignore
    except Exception:
        print("尚未安裝 requests，將使用 sample mode。")
        return None

    try:
        response = requests.get(url, timeout=config["api"].get("timeout_seconds", 20))
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "csv" in content_type or url.lower().endswith(".csv"):
            df = pd.read_csv(StringIO(response.text))
        else:
            df = _records_to_frame(response.json())
        df = _rename_aliases(df)
        missing = API_REQUIRED_COLUMNS - set(df.columns)
        if missing:
            print(f"API 欄位不足，將使用 fallback：{sorted(missing)}")
            return None
    except Exception as exc:
        print(f"API 讀取失敗，將使用 sample data fallback：{exc}")
        return None

    if output_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = project_path(config["data"]["raw_dir"], f"aqi_raw_{stamp}.csv")
    out = ensure_parent(output_path)
    df.to_csv(out, index=False, encoding="utf-8")
    print(f"API 資料已儲存：{out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    fetch_aqi_data()


if __name__ == "__main__":
    main()
