from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.export_web import build_provenance


def test_model_provenance_counts_hourly_api_rows_and_retains_native_model_resolution(tmp_path: Path) -> None:
    metadata_path = tmp_path / "source_metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "provider": "open_meteo_cams_global",
                "status": "success",
                "data_source": "Model Estimate",
                "is_simulated_data": False,
                "row_count": 48,
                "native_temporal_resolution_hours": 3,
                "api_output_temporal_resolution_hours": 1,
                "spatial_resolution_km": 45,
                "model_name": "CAMS Global Atmospheric Composition Forecasts",
                "aqi_standard": "U.S. EPA AQI",
                "timezone": "Asia/Taipei",
                "ozone_unit": "μg/m³",
                "data_file_sha256": "a" * 64,
                "schema_sha256": "b" * 64,
            }
        ),
        encoding="utf-8",
    )
    times = pd.date_range("2026-10-01T00:00:00+08:00", periods=49, freq="h")
    cleaned = pd.DataFrame({"datetime": times, "site_name": ["臺北網格"] * len(times)})

    payload = build_provenance(cleaned, {"reports": {"source_metadata_file": str(metadata_path)}}, tmp_path / "sample")

    # The source has 48 API hourly rows across a 49-hour expected interval.
    assert payload["rows"] == 48
    assert payload["native_temporal_resolution_hours"] == 3
    assert payload["api_output_temporal_resolution_hours"] == 1
    assert payload["completeness"] == 0.9796
    assert payload["is_model_estimate"] is True
    assert payload["is_simulated"] is False
