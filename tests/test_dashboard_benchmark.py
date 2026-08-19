from __future__ import annotations

from src.benchmark_dashboard import benchmark_dashboard


def test_dashboard_benchmark_reports_reproducible_measurements() -> None:
    result = benchmark_dashboard()

    assert {"cold_load_ms", "warm_load_ms", "scope_build_ms", "feature_rows"} <= set(result)
    assert result["cold_load_ms"] >= 0
    assert result["warm_load_ms"] >= 0
    assert result["scope_build_ms"] >= 0
    assert result["feature_rows"] >= 0
    assert result["cache_reused"] is True or result["feature_rows"] == 0