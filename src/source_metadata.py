from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlsplit, urlunsplit

import pandas as pd

from src.utils import write_json


SOURCE_METADATA_VERSION = "1.0"
DEFAULT_METADATA_PATH = Path("reports/metrics/source_metadata.json")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalise_timestamp(value: datetime | date | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, datetime.min.time())
    if isinstance(value, datetime):
        timestamp = value
    else:
        try:
            timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return str(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def redact_source_url(url: str | None) -> str:
    """Keep only the public endpoint identity; remove credentials and request data."""
    if not url:
        return ""
    try:
        parsed = urlsplit(str(url))
        hostname = parsed.hostname
        if not hostname or parsed.scheme not in {"http", "https"}:
            return ""
        netloc = hostname
        try:
            port = parsed.port
        except ValueError:
            port = None
        if port is not None and not ((parsed.scheme == "https" and port == 443) or (parsed.scheme == "http" and port == 80)):
            netloc = f"{netloc}:{port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path.rstrip("/") or "/", "", ""))
    except (TypeError, ValueError):
        return ""


def schema_sha256(columns: Iterable[object] | None) -> str:
    canonical = "\n".join(sorted({str(column).strip() for column in (columns or []) if str(column).strip()}))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str | None:
    """Return a file digest used to bind provenance to the exact input artifact."""
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def frame_summary(frame: pd.DataFrame | None) -> dict[str, Any]:
    if frame is None:
        return {"row_count": 0, "datetime_range": {"min": None, "max": None}, "schema_columns": [], "schema_sha256": schema_sha256([])}
    datetime_range = {"min": None, "max": None}
    if "datetime" in frame.columns and not frame.empty:
        timestamps = pd.to_datetime(frame["datetime"], errors="coerce").dropna()
        if not timestamps.empty:
            datetime_range = {
                "min": _normalise_timestamp(timestamps.min().to_pydatetime()),
                "max": _normalise_timestamp(timestamps.max().to_pydatetime()),
            }
    columns = [str(column) for column in frame.columns]
    return {
        "row_count": int(len(frame)),
        "datetime_range": datetime_range,
        "schema_columns": sorted(set(columns)),
        "schema_sha256": schema_sha256(columns),
    }


def _source_label(mode: str, status: str, data_source: str | None) -> tuple[str, bool]:
    if data_source in {"Sample Data", "API Data"}:
        return data_source, data_source == "Sample Data"
    if mode == "sample" or status == "fallback":
        return "Sample Data", True
    if mode == "api" and status == "success":
        return "API Data", False
    return "Unknown", False


def build_source_metadata(
    *,
    provider: str,
    mode: str,
    status: str,
    row_count: int = 0,
    datetime_range: Mapping[str, Any] | None = None,
    schema_columns: Iterable[object] | None = None,
    schema_hash: str | None = None,
    source_url: str | None = None,
    requested_at_utc: datetime | str | None = None,
    fetched_at_utc: datetime | str | None = None,
    fallback_reason: str | None = None,
    error_type: str | None = None,
    http_status: int | None = None,
    data_source: str | None = None,
    is_simulated_data: bool | None = None,
    data_file_sha256: str | None = None,
) -> dict[str, Any]:
    label, simulated = _source_label(mode, status, data_source)
    columns = sorted({str(column) for column in (schema_columns or [])})
    return {
        "metadata_version": SOURCE_METADATA_VERSION,
        "provider": str(provider or "unknown"),
        "mode": str(mode or "unknown"),
        "status": str(status or "unknown"),
        "data_source": label,
        "is_simulated_data": simulated if is_simulated_data is None else bool(is_simulated_data),
        "source_url": redact_source_url(source_url),
        "requested_at_utc": _normalise_timestamp(requested_at_utc),
        "fetched_at_utc": _normalise_timestamp(fetched_at_utc),
        "row_count": int(row_count),
        "datetime_range": dict(datetime_range or {"min": None, "max": None}),
        "schema_columns": columns,
        "schema_sha256": schema_hash or schema_sha256(columns),
        "data_file_sha256": data_file_sha256,
        "fallback_reason": fallback_reason,
        "error_type": error_type,
        "http_status": int(http_status) if http_status is not None else None,
    }


def unknown_source_metadata(reason: str = "metadata_missing") -> dict[str, Any]:
    return build_source_metadata(
        provider="unknown",
        mode="unknown",
        status="unknown",
        fallback_reason=reason,
    )


def load_source_metadata(config: Mapping[str, Any], *, root: str | Path | None = None) -> dict[str, Any]:
    """Read provenance safely; malformed or missing metadata is explicitly unknown."""
    reports = config.get("reports", {}) if isinstance(config, Mapping) else {}
    configured = reports.get("source_metadata_file", DEFAULT_METADATA_PATH) if isinstance(reports, Mapping) else DEFAULT_METADATA_PATH
    path = Path(configured)
    if root is not None and not path.is_absolute():
        path = Path(root) / path
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError, TypeError):
        return unknown_source_metadata("metadata_missing_or_invalid")
    return dict(value) if isinstance(value, dict) else unknown_source_metadata("metadata_schema_invalid")


def write_source_metadata(path: str | Path, payload: Mapping[str, Any]) -> Path:
    target = Path(path)
    write_json(target, dict(payload))
    return target


def resolve_effective_run_mode(
    requested_mode: str,
    source_metadata: Mapping[str, Any] | None,
    input_path: Path | None = None,
) -> str:
    """Return API only when the source contract proves a successful API fetch."""
    metadata = source_metadata or {}
    if input_path is None:
        return "sample"
    expected_digest = str(metadata.get("data_file_sha256") or "")
    actual_digest = file_sha256(input_path)
    if (
        requested_mode == "api"
        and metadata.get("status") == "success"
        and metadata.get("data_source") == "API Data"
        and metadata.get("is_simulated_data") is False
        and expected_digest
        and actual_digest == expected_digest
    ):
        return "api"
    return "sample"
