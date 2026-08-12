from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from src.app_helpers import add_display_columns, filter_by_site_and_date
from src.dashboard.context import DashboardData, DashboardMetrics, FilteredData, FilterState
from src.utils import resolve_path


@dataclass(frozen=True)
class FileSignature:
    path: str
    modified_ns: int
    size: int


def file_signature(path: str | Path) -> FileSignature | None:
    resolved = Path(path).expanduser().resolve()
    try:
        stat = resolved.stat()
    except OSError:
        return None
    return FileSignature(str(resolved), stat.st_mtime_ns, stat.st_size)


@lru_cache(maxsize=32)
def _read_csv_cached(signature: FileSignature, parse_dates: tuple[str, ...]) -> pd.DataFrame:
    try:
        return pd.read_csv(signature.path, parse_dates=list(parse_dates) or None)
    except (OSError, ValueError, pd.errors.ParserError):
        return pd.DataFrame()


@lru_cache(maxsize=32)
def _read_json_cached(signature: FileSignature) -> dict[str, Any]:
    try:
        value = json.loads(Path(signature.path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def clear_artifact_cache() -> None:
    _read_csv_cached.cache_clear()
    _read_json_cached.cache_clear()


def read_csv_versioned(
    path: str | Path,
    parse_dates: tuple[str, ...] | list[str] = (),
) -> pd.DataFrame:
    signature = file_signature(path)
    if signature is None:
        return pd.DataFrame()
    return _read_csv_cached(signature, tuple(parse_dates)).copy(deep=True)


def read_json_versioned(path: str | Path) -> dict[str, Any]:
    signature = file_signature(path)
    if signature is None:
        return {}
    return dict(_read_json_cached(signature))


def load_dashboard_artifacts(config: dict[str, Any]) -> tuple[DashboardData, DashboardMetrics]:
    data = DashboardData(
        features=add_display_columns(
            read_csv_versioned(resolve_path(config, "data.features_file"), ("datetime",))
        ),
        predictions=add_display_columns(
            read_csv_versioned(resolve_path(config, "data.predictions_file"), ("datetime",))
        ),
        anomalies=add_display_columns(
            read_csv_versioned(resolve_path(config, "data.anomaly_file"), ("datetime",))
        ),
        events=add_display_columns(
            read_csv_versioned(
                resolve_path(config, "data.events_file"),
                ("datetime", "end_datetime", "peak_datetime"),
            )
        ),
    )
    metrics_dir = resolve_path(config, "reports.metrics_dir")
    metrics = DashboardMetrics(
        predictor=read_json_versioned(metrics_dir / "predictor_metrics.json"),
        anomaly=read_json_versioned(metrics_dir / "anomaly_metrics.json"),
        backtest=read_json_versioned(metrics_dir / "backtest_metrics.json"),
        confidence=read_json_versioned(resolve_path(config, "reports.confidence_file")),
        data_health=read_json_versioned(metrics_dir / "data_health.json"),
        evaluation=read_json_versioned(metrics_dir / "evaluation_summary.json"),
    )
    return data, metrics


def _filter_frame(
    frame: pd.DataFrame,
    filters: FilterState,
    *,
    include_county: bool,
    include_site: bool,
) -> pd.DataFrame:
    return filter_by_site_and_date(
        frame,
        site_name=filters.site_name if include_site else None,
        county_display=filters.county if include_county else None,
        start_datetime=filters.start_date,
        end_datetime=filters.end_date,
    )


def _scope(
    data: DashboardData,
    filters: FilterState,
    *,
    include_county: bool,
    include_site: bool,
) -> DashboardData:
    return DashboardData(
        features=_filter_frame(data.features, filters, include_county=include_county, include_site=include_site),
        predictions=_filter_frame(data.predictions, filters, include_county=include_county, include_site=include_site),
        anomalies=_filter_frame(data.anomalies, filters, include_county=include_county, include_site=include_site),
        events=_filter_frame(data.events, filters, include_county=include_county, include_site=include_site),
    )


def build_filtered_data(data: DashboardData, filters: FilterState) -> FilteredData:
    return FilteredData(
        source=data,
        selected=_scope(data, filters, include_county=True, include_site=True),
        regional=_scope(data, filters, include_county=True, include_site=False),
        comparison=_scope(data, filters, include_county=False, include_site=False),
    )
