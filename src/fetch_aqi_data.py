from __future__ import annotations

import argparse
import ipaddress
import json
import os
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from src.utils import load_config, project_path, write_csv


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
MAX_API_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_API_TIMEOUT_SECONDS = 60
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _validate_api_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
    except ValueError as exc:
        raise ValueError("API URL is malformed") from exc
    if parsed.scheme not in {"https", "http"} or not hostname:
        raise ValueError("API URL must use HTTPS and include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("API URL must not include embedded credentials")
    if parsed.fragment:
        raise ValueError("API URL must not include a URL fragment")

    normalized_host = hostname.rstrip(".").lower()
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None

    if address is not None:
        is_loopback = address.is_loopback
        if not address.is_global and not is_loopback:
            raise ValueError("API host must be public or local loopback")
        if parsed.scheme == "http" and not is_loopback:
            raise ValueError("Non-local API URLs must use HTTPS")
    elif parsed.scheme == "http" and normalized_host not in LOCAL_HOSTS:
        raise ValueError("Non-local API URLs must use HTTPS")
    return url


def _read_limited_response(response: Any, max_bytes: int = MAX_API_RESPONSE_BYTES) -> bytes:
    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        raise ValueError("API response exceeds the maximum allowed size")
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("API response exceeds the maximum allowed size")
        chunks.append(chunk)
    return b"".join(chunks)


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
        _validate_api_url(url)
        configured_timeout = float(config["api"].get("timeout_seconds", 20))
        timeout = (5, min(max(configured_timeout, 1), MAX_API_TIMEOUT_SECONDS))
        response = requests.get(url, timeout=timeout, stream=True, allow_redirects=False)
        if 300 <= response.status_code < 400:
            response.close()
            raise ValueError("API redirects are not allowed")
        response.raise_for_status()
        try:
            content = _read_limited_response(response)
        finally:
            response.close()
        content_type = response.headers.get("content-type", "").lower()
        response_text = content.decode(response.encoding or "utf-8", errors="replace")
        if "csv" in content_type or url.lower().endswith(".csv"):
            df = pd.read_csv(StringIO(response_text))
        else:
            df = _records_to_frame(json.loads(response_text))
        df = _rename_aliases(df)
        missing = API_REQUIRED_COLUMNS - set(df.columns)
        if missing:
            print(f"API 欄位不足，將使用 fallback：{sorted(missing)}")
            return None
    except Exception as exc:
        print(f"API 讀取失敗（{type(exc).__name__}），將使用 sample data fallback。")
        return None

    if output_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = project_path(config["data"]["raw_dir"], f"aqi_raw_{stamp}.csv")
    out = Path(output_path)
    write_csv(df, out, index=False, encoding="utf-8")
    print(f"API 資料已儲存：{out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    fetch_aqi_data()


if __name__ == "__main__":
    main()
