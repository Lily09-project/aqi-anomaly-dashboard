from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.source_metadata import (
    build_source_metadata,
    file_sha256,
    frame_summary,
    load_source_metadata,
    redact_source_url,
    resolve_effective_run_mode,
    schema_sha256,
    write_source_metadata,
)


def test_redact_source_url_removes_credentials_query_and_fragment() -> None:
    value = redact_source_url("https://user:secret@example.com/aqi?token=private#debug")

    assert value == "https://example.com/aqi"


def test_source_metadata_marks_sample_data() -> None:
    payload = build_source_metadata(
        provider="sample_generator",
        mode="sample",
        status="success",
        row_count=10,
        datetime_range={"min": "2026-08-01T00:00:00", "max": "2026-08-01T09:00:00"},
    )

    assert payload["data_source"] == "Sample Data"
    assert payload["is_simulated_data"] is True
    assert payload["fallback_reason"] is None
    assert "token" not in json.dumps(payload)


def test_frame_summary_is_content_free_and_schema_hash_is_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "datetime": pd.to_datetime(["2026-08-01 00:00", "2026-08-01 01:00"]),
            "aqi": [40, 42],
            "site_name": ["A", "A"],
        }
    )

    summary = frame_summary(frame)

    assert summary["row_count"] == 2
    assert summary["datetime_range"]["min"].startswith("2026-08-01T00:00")
    assert summary["datetime_range"]["max"].startswith("2026-08-01T01:00")
    assert summary["schema_sha256"] == schema_sha256(["site_name", "aqi", "datetime"])
    assert "40" not in json.dumps(summary)


def test_source_metadata_round_trip_and_effective_mode(tmp_path: Path) -> None:
    target = tmp_path / "source_metadata.json"
    input_path = tmp_path / "api.csv"
    input_path.write_text("datetime,aqi\n2026-08-20 00:00,42\n", encoding="utf-8")
    payload = build_source_metadata(
        provider="moenv_aqx_p_432",
        mode="api",
        status="success",
        row_count=2,
        data_source="API Data",
        is_simulated_data=False,
        data_file_sha256=file_sha256(input_path),
    )
    write_source_metadata(target, payload)

    loaded = load_source_metadata({"reports": {"source_metadata_file": target}})

    assert loaded["data_source"] == "API Data"
    assert resolve_effective_run_mode("api", loaded, input_path) == "api"
    assert resolve_effective_run_mode("api", {"status": "fallback", "data_source": "Sample Data"}) == "sample"


def test_stale_api_metadata_cannot_label_a_different_input_as_api(tmp_path: Path) -> None:
    input_path = tmp_path / "api.csv"
    input_path.write_text("datetime,aqi\n2026-08-20 00:00,42\n", encoding="utf-8")
    metadata = build_source_metadata(
        provider="moenv_aqx_p_432",
        mode="api",
        status="success",
        data_source="API Data",
        is_simulated_data=False,
        data_file_sha256=file_sha256(input_path),
    )

    input_path.write_text("datetime,aqi\n2026-08-20 00:00,99\n", encoding="utf-8")

    assert resolve_effective_run_mode("api", metadata, input_path) == "sample"


def test_missing_source_metadata_is_explicitly_unknown(tmp_path: Path) -> None:
    loaded = load_source_metadata({"reports": {"source_metadata_file": "missing.json"}}, root=tmp_path)

    assert loaded["status"] == "unknown"
    assert loaded["fallback_reason"] == "metadata_missing_or_invalid"
