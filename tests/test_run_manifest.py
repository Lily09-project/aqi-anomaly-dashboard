from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from src.run_manifest import build_run_manifest, sha256_file, write_run_manifest


def _config() -> dict:
    return {
        "project": {"name": "Test AQI Dashboard"},
        "random_state": 42,
        "train": {"feature_columns": ["aqi", "lag_1_aqi", "rolling_3h_aqi"]},
    }


def test_run_manifest_records_contract_and_artifact_hash(tmp_path: Path) -> None:
    config = _config()
    config_path = tmp_path / "config.yaml"
    config_path.write_text("project:\n  name: Test AQI Dashboard\n", encoding="utf-8")
    artifact = tmp_path / "reports" / "metrics" / "predictor_metrics.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text('{"mae": 1.25}\n', encoding="utf-8")

    manifest = build_run_manifest(
        tmp_path,
        config=config,
        run_mode="sample",
        artifacts=["reports/metrics/predictor_metrics.json"],
        generated_at="2026-08-19T00:00:00Z",
    )

    expected_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert sha256_file(artifact) == expected_hash
    assert manifest["run"]["data_source"] == "Sample Data"
    assert manifest["run"]["is_simulated_data"] is True
    assert manifest["data_contract"]["target"] == "target_next_hour_aqi"
    assert manifest["data_contract"]["feature_contract_valid"] is True
    assert "target_next_hour_aqi" not in manifest["data_contract"]["feature_columns"]
    assert manifest["artifacts"] == [
        {
            "path": "reports/metrics/predictor_metrics.json",
            "exists": True,
            "size_bytes": artifact.stat().st_size,
            "sha256": expected_hash,
        }
    ]
    assert manifest["run"]["config"]["sha256"] == hashlib.sha256(config_path.read_bytes()).hexdigest()
    json.dumps(manifest, ensure_ascii=False)


def test_write_run_manifest_is_valid_json_and_marks_missing_outputs(tmp_path: Path) -> None:
    manifest_path = write_run_manifest(
        tmp_path,
        config=_config(),
        run_mode="api",
        output_path="reports/metrics/run_manifest.json",
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_path.is_file()
    assert payload["run"]["data_source"] == "API Data"
    assert payload["run"]["is_simulated_data"] is False
    assert any(item["exists"] is False for item in payload["artifacts"])
    assert payload["project"]["git_revision"]


def test_write_run_manifest_rejects_output_outside_project(tmp_path: Path) -> None:
    outside_path = tmp_path.parent / "outside-manifest.json"
    with pytest.raises(ValueError, match="inside the project root"):
        write_run_manifest(tmp_path, config=_config(), run_mode="sample", output_path=outside_path)
