from __future__ import annotations

import argparse
import ipaddress
import json
import os
import socket
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pandas as pd

from src.source_metadata import build_source_metadata, file_sha256, frame_summary, write_source_metadata
from src.utils import load_config, project_path, resolve_path, write_csv


ALIASES = {
    "site_name": ["site_name", "sitename", "site", "SiteName", "station", "測站", "測站名稱"],
    "county": ["county", "County", "city", "縣市"],
    "aqi": ["aqi", "AQI"],
    "pm25": ["pm2.5", "pm25", "PM2.5", "PM2.5_AVG", "pm2_5"],
    "pm10": ["pm10", "PM10"],
    "o3": ["o3", "O3"],
    "co": ["co", "CO"],
    "wind_speed": ["wind_speed", "WindSpeed", "windspeed", "WIND_SPEED"],
    "wind_directions": ["wind_directions", "WindDirec", "winddirec", "WIND_DIREC"],
    "datetime": ["datetime", "publishtime", "monitordate", "datacreationdate", "DataCreationDate", "發布時間"],
}

API_REQUIRED_COLUMNS = set(ALIASES)
MAX_API_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_API_TIMEOUT_SECONDS = 60
MAX_API_LIMIT = 10000
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
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("API URL has an invalid port") from exc

    normalized_host = hostname.rstrip(".").lower()
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            address = ipaddress.ip_address(socket.inet_aton(hostname))
        except (OSError, ValueError):
            address = None

    if address is not None:
        is_loopback = address.is_loopback
        if is_loopback:
            if parsed.scheme != "http" or normalized_host not in LOCAL_HOSTS:
                raise ValueError("Only canonical loopback HTTP endpoints are allowed")
        else:
            if not address.is_global:
                raise ValueError("API host must be public or local loopback")
            if parsed.scheme == "http":
                raise ValueError("Non-local API URLs must use HTTPS")
    elif normalized_host in LOCAL_HOSTS:
        if parsed.scheme != "http":
            raise ValueError("Only canonical loopback HTTP endpoints are allowed")
    elif parsed.scheme == "http":
        raise ValueError("Non-local API URLs must use HTTPS")
    return url


def _read_limited_response(response: Any, max_bytes: int = MAX_API_RESPONSE_BYTES) -> bytes:
    headers = getattr(response, "headers", {}) or {}
    content_length = headers.get("content-length")
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


def _metadata_target(config: dict[str, Any], metadata_path: str | Path | None) -> Path:
    if metadata_path is not None:
        return Path(metadata_path)
    reports = config.get("reports", {})
    configured = reports.get("source_metadata_file", "reports/metrics/source_metadata.json")
    return resolve_path(config, "reports.source_metadata_file") if "source_metadata_file" in reports else project_path(configured)


def _write_fetch_metadata(
    target: Path,
    *,
    provider: str,
    status: str,
    source_url: str,
    requested_at: str,
    frame: pd.DataFrame | None = None,
    fallback_reason: str | None = None,
    error_type: str | None = None,
    http_status: int | None = None,
    data_file_sha256: str | None = None,
) -> dict[str, Any]:
    summary = frame_summary(frame)
    metadata = build_source_metadata(
        provider=provider,
        mode="api",
        status=status,
        row_count=summary["row_count"],
        datetime_range=summary["datetime_range"],
        schema_columns=summary["schema_columns"],
        schema_hash=summary["schema_sha256"],
        source_url=source_url,
        requested_at_utc=requested_at,
        fetched_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z") if frame is not None else None,
        data_file_sha256=data_file_sha256,
        fallback_reason=fallback_reason,
        error_type=error_type,
        http_status=http_status,
    )
    write_source_metadata(target, metadata)
    return metadata


def _api_limit(config: dict[str, Any]) -> int:
    raw_value = os.getenv("AQI_API_LIMIT") or config.get("api", {}).get("limit", 1000)
    try:
        return max(1, min(int(raw_value), MAX_API_LIMIT))
    except (TypeError, ValueError):
        return 1000


def fetch_aqi_data(output_path: str | Path | None = None, metadata_path: str | Path | None = None) -> Path | None:
    config = load_config()
    requested_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    api_config = config.get("api", {})
    provider = str(api_config.get("provider", "moenv_aqx_p_432"))
    metadata_target = _metadata_target(config, metadata_path)

    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        load_dotenv = None
    if load_dotenv is not None:
        try:
            load_dotenv()
        except (OSError, UnicodeError):
            pass

    url = str(api_config.get("url") or os.getenv("AQI_API_URL") or "").strip()
    if not url:
        _write_fetch_metadata(
            metadata_target,
            provider=provider,
            status="fallback",
            source_url="",
            requested_at=requested_at,
            fallback_reason="api_url_not_configured",
        )
        print("未設定 API URL，將使用 sample mode。")
        return None

    try:
        import requests  # type: ignore
    except Exception as exc:
        _write_fetch_metadata(
            metadata_target,
            provider=provider,
            status="fallback",
            source_url=url,
            requested_at=requested_at,
            fallback_reason="requests_not_installed",
            error_type=type(exc).__name__,
        )
        print("尚未安裝 requests，將使用 sample mode。")
        return None

    response: Any = None
    try:
        _validate_api_url(url)
        configured_timeout = float(api_config.get("timeout_seconds", 20))
        timeout = (5, min(max(configured_timeout, 1), MAX_API_TIMEOUT_SECONDS))
        params: dict[str, object] = {"limit": _api_limit(config)}
        api_key = os.getenv("AQI_API_KEY", "").strip()
        if api_key:
            params["api_key"] = api_key
        response = requests.get(url, params=params, timeout=timeout, stream=True, allow_redirects=False)
        response_status = getattr(response, "status_code", None)
        if response_status is not None and 300 <= response_status < 400:
            raise ValueError("API redirects are not allowed")
        response.raise_for_status()
        try:
            content = _read_limited_response(response)
        finally:
            response.close()
        headers = getattr(response, "headers", {}) or {}
        content_type = str(headers.get("content-type", "")).lower()
        encoding = getattr(response, "encoding", None) or "utf-8"
        response_text = content.decode(encoding, errors="replace")
        if "csv" in content_type or url.lower().endswith(".csv"):
            frame = pd.read_csv(StringIO(response_text))
        else:
            frame = _records_to_frame(json.loads(response_text))
        frame = _rename_aliases(frame)
        missing = API_REQUIRED_COLUMNS - set(frame.columns)
        if missing:
            _write_fetch_metadata(
                metadata_target,
                provider=provider,
                status="fallback",
                source_url=url,
                requested_at=requested_at,
                frame=frame,
                fallback_reason="required_columns_missing",
                http_status=response_status,
            )
            print(f"API 欄位不足，將使用 fallback：{sorted(missing)}")
            return None
    except Exception as exc:
        _write_fetch_metadata(
            metadata_target,
            provider=provider,
            status="fallback",
            source_url=url,
            requested_at=requested_at,
            fallback_reason="api_request_failed",
            error_type=type(exc).__name__,
            http_status=getattr(response, "status_code", None),
        )
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        print(f"API 讀取失敗（{type(exc).__name__}），將使用 sample data fallback。")
        return None

    if output_path is None:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = project_path(config["data"]["raw_dir"], f"aqi_raw_{stamp}.csv")
    out = Path(output_path)
    write_csv(frame, out, index=False, encoding="utf-8")
    _write_fetch_metadata(
        metadata_target,
        provider=provider,
        status="success",
        source_url=url,
        requested_at=requested_at,
        frame=frame,
        http_status=getattr(response, "status_code", None),
        data_file_sha256=file_sha256(out),
    )
    print(f"API 資料已儲存：{out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    parser.add_argument("--metadata", default=None)
    args = parser.parse_args()
    fetch_aqi_data(output_path=args.output, metadata_path=args.metadata)


if __name__ == "__main__":
    main()
