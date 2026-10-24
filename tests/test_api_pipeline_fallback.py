from __future__ import annotations

from pathlib import Path

import run_all


def test_api_failure_without_raw_data_runs_sample_pipeline(monkeypatch, tmp_path: Path) -> None:
    sample_path = tmp_path / "sample" / "sample_aqi.csv"
    metadata = {
        "status": "fallback",
        "data_source": "Sample Data",
        "is_simulated_data": True,
        "fallback_reason": "api_request_failed",
    }
    calls: list[str] = []
    paths = {
        "data.raw_dir": tmp_path / "raw",
        "data.sample_file": sample_path,
        "data.cleaned_file": tmp_path / "processed" / "aqi_cleaned.csv",
    }

    monkeypatch.setattr(run_all, "fetch_aqi_data", lambda: None)
    monkeypatch.setattr(run_all, "latest_csv", lambda _path: None)
    monkeypatch.setattr(run_all, "load_config", lambda: {})
    monkeypatch.setattr(run_all, "resolve_path", lambda _config, key: paths[key])
    monkeypatch.setattr(run_all, "generate_sample_aqi", lambda: calls.append("sample"))
    monkeypatch.setattr(run_all, "load_source_metadata", lambda _config, root: metadata)
    monkeypatch.setattr(run_all, "preprocess", lambda **kwargs: calls.append(f"preprocess:{kwargs['mode']}:{kwargs['input_path'] == sample_path}"))
    monkeypatch.setattr(run_all, "export", lambda target: calls.append(f"export:{target.name}") or {"overview.json": "x"})

    hashes = run_all.run("api", out_dir=tmp_path / "web-data")

    assert hashes == {"overview.json": "x"}
    # The API failed and no raw data existed, so the run is labelled as sample data.
    assert calls == ["sample", "preprocess:sample:True", "export:web-data"]
    assert paths["data.raw_dir"].is_dir()


def test_sample_mode_never_calls_the_api(monkeypatch, tmp_path: Path) -> None:
    def forbidden():
        raise AssertionError("sample mode must not fetch")

    monkeypatch.setattr(run_all, "fetch_aqi_data", forbidden)
    monkeypatch.setattr(run_all, "generate_sample_aqi", lambda: None)
    monkeypatch.setattr(run_all, "load_source_metadata", lambda _config, root: {"status": "success", "data_source": "Sample Data"})
    monkeypatch.setattr(run_all, "preprocess", lambda **kwargs: None)
    monkeypatch.setattr(run_all, "export", lambda target: {})
    monkeypatch.setattr(run_all, "resolve_path", lambda _config, key: tmp_path / key.replace(".", "_"))
    monkeypatch.setattr(run_all, "load_config", lambda: {})

    assert run_all.run("sample", out_dir=tmp_path / "out") == {}
