from __future__ import annotations

from pathlib import Path

import run_all


def test_api_failure_without_raw_data_runs_sample_pipeline(monkeypatch, tmp_path: Path) -> None:
    sample_path = tmp_path / "sample_aqi.csv"
    metadata = {
        "status": "fallback",
        "data_source": "Sample Data",
        "is_simulated_data": True,
        "fallback_reason": "api_request_failed",
    }
    calls: list[str] = []

    monkeypatch.setattr(run_all, "_ensure_dirs", lambda: calls.append("dirs"))
    monkeypatch.setattr(run_all, "fetch_aqi_data", lambda: None)
    monkeypatch.setattr(run_all, "latest_csv", lambda _path: None)
    monkeypatch.setattr(
        run_all,
        "load_config",
        lambda: {"data": {"raw_dir": "data/raw", "sample_file": str(sample_path)}},
    )
    monkeypatch.setattr(
        run_all,
        "resolve_path",
        lambda config, key: Path(config["data"][key.split(".")[-1]]),
    )
    monkeypatch.setattr(
        run_all,
        "generate_sample_aqi",
        lambda: sample_path.write_text("sample", encoding="utf-8"),
    )
    monkeypatch.setattr(run_all, "load_source_metadata", lambda _config, root: metadata)
    monkeypatch.setattr(
        run_all,
        "preprocess",
        lambda **kwargs: calls.append(f"preprocess:{kwargs['mode']}"),
    )
    monkeypatch.setattr(run_all, "build_features", lambda: calls.append("features"))
    monkeypatch.setattr(run_all, "train_predictor", lambda: calls.append("predictor"))
    monkeypatch.setattr(run_all, "train_anomaly_model", lambda: calls.append("anomaly"))
    monkeypatch.setattr(
        run_all,
        "evaluate",
        lambda **kwargs: calls.append(f"evaluate:{kwargs['source_metadata']['status']}"),
    )
    monkeypatch.setattr(
        run_all,
        "write_run_manifest",
        lambda _root, **kwargs: calls.append(
            f"manifest:{kwargs['run_mode']}:{kwargs['source_metadata']['data_source']}"
        ),
    )
    monkeypatch.setattr(run_all, "run_smoke_test", lambda: calls.append("smoke"))
    monkeypatch.setattr(run_all, "_output_summary", lambda: [sample_path])

    outputs = run_all.run("api")

    assert sample_path in outputs
    assert "preprocess:sample" in calls
    assert "evaluate:fallback" in calls
    assert "manifest:sample:Sample Data" in calls
