from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.dashboard.context import FilterState
from src.dashboard.data_service import (
    _read_csv_cached,
    _read_json_cached,
    build_filtered_data,
    clear_artifact_cache,
    load_dashboard_artifacts,
)
from src.utils import load_config


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)


def benchmark_dashboard(config: dict[str, Any] | None = None) -> dict[str, float | int | bool]:
    """Measure artifact loading and scope construction without fixed speed thresholds."""
    cfg = config or load_config()
    clear_artifact_cache()

    started_at = perf_counter()
    data, _ = load_dashboard_artifacts(cfg)
    cold_load_ms = _elapsed_ms(started_at)

    csv_hits_before = _read_csv_cached.cache_info().hits
    json_hits_before = _read_json_cached.cache_info().hits
    started_at = perf_counter()
    warm_data, _ = load_dashboard_artifacts(cfg)
    warm_load_ms = _elapsed_ms(started_at)
    cache_reused = (
        _read_csv_cached.cache_info().hits > csv_hits_before
        or _read_json_cached.cache_info().hits > json_hits_before
    )

    filters = FilterState(
        county=None,
        site_name=None,
        site_display="All stations",
        start_date=None,
        end_date=None,
    )
    started_at = perf_counter()
    build_filtered_data(warm_data, filters)
    scope_build_ms = _elapsed_ms(started_at)

    return {
        "cold_load_ms": cold_load_ms,
        "warm_load_ms": warm_load_ms,
        "scope_build_ms": scope_build_ms,
        "feature_rows": int(len(data.features)),
        "cache_reused": cache_reused,
    }


def main() -> None:
    print(json.dumps(benchmark_dashboard(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()