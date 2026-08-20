from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.utils import write_json


HISTORY_VERSION = "1.0"
SNAPSHOT_VERSION = "1.0"


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 6)


def _signal_shift(monitoring: Mapping[str, Any], column: str) -> float | None:
    signals = monitoring.get("signals", [])
    if not isinstance(signals, list):
        return None
    for item in signals:
        signal = _mapping(item)
        if signal.get("column") == column:
            return _number(signal.get("standardized_mean_shift"))
    return None


def _monitoring_action(status: str, retraining_recommended: bool) -> str:
    if retraining_recommended or status == "critical":
        return "review_retraining"
    if status == "warning":
        return "investigate"
    if status == "insufficient_data":
        return "collect_more_data"
    return "observe"


def _utc_timestamp(value: str | None = None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_monitoring_snapshot(
    monitoring: Mapping[str, Any],
    *,
    data_end: str,
    data_source: str,
    model_name: str,
    recorded_at_utc: str | None = None,
) -> dict[str, Any]:
    """Flatten one monitoring run into a stable, reviewer-readable record."""
    prediction = _mapping(monitoring.get("prediction"))
    coverage = _mapping(monitoring.get("coverage"))
    coverage_80 = _mapping(coverage.get("80"))
    coverage_95 = _mapping(coverage.get("95"))
    retraining = _mapping(monitoring.get("retraining"))
    status = str(monitoring.get("status", "insufficient_data"))
    recommended = bool(retraining.get("recommended", False))
    reasons = retraining.get("reasons", [])
    reason_list = [str(reason) for reason in reasons] if isinstance(reasons, list) else []

    identity = "|".join(
        (
            str(data_end),
            str(data_source),
            str(model_name),
            str(monitoring.get("monitoring_version", "unknown")),
        )
    )
    snapshot_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return {
        "snapshot_version": SNAPSHOT_VERSION,
        "snapshot_id": snapshot_id,
        "recorded_at_utc": _utc_timestamp(recorded_at_utc),
        "data_end": str(data_end),
        "data_source": str(data_source),
        "model_name": str(model_name),
        "status": status,
        "action": _monitoring_action(status, recommended),
        "reference_mae": _number(prediction.get("reference_mae")),
        "current_mae": _number(prediction.get("current_mae")),
        "mae_change_pct": _number(prediction.get("mae_change_pct")),
        "coverage_80": _number(coverage_80.get("current")),
        "coverage_95": _number(coverage_95.get("current")),
        "aqi_shift": _signal_shift(monitoring, "aqi"),
        "pm25_shift": _signal_shift(monitoring, "pm25"),
        "retraining_recommended": recommended,
        "reasons": reason_list,
    }


def _read_entries(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if not isinstance(payload, dict) or not isinstance(payload.get("entries"), list):
        return []
    return [entry for entry in payload["entries"] if isinstance(entry, dict)]


def update_monitoring_history(
    path: str | Path,
    snapshot: Mapping[str, Any],
    *,
    max_entries: int = 90,
) -> dict[str, Any]:
    """Insert or replace a snapshot, retain the latest records, and write atomically."""
    if max_entries < 1:
        raise ValueError("max_entries must be at least 1")
    history_path = Path(path)
    snapshot_record = dict(snapshot)
    snapshot_id = str(snapshot_record.get("snapshot_id", ""))
    if not snapshot_id:
        raise ValueError("snapshot_id is required")

    entries = [
        entry
        for entry in _read_entries(history_path)
        if str(entry.get("snapshot_id", "")) != snapshot_id
    ]
    entries.append(snapshot_record)
    entries.sort(key=lambda entry: str(entry.get("recorded_at_utc", "")))
    entries = entries[-max_entries:]
    payload = {
        "history_version": HISTORY_VERSION,
        "updated_at_utc": str(snapshot_record.get("recorded_at_utc", "")),
        "entry_count": len(entries),
        "entries": entries,
    }
    write_json(history_path, payload)
    return payload
