from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from run_all import run
from src import export_web
from src.analytics import whatif

FILES = ("overview.json", "propagation.json", "anomalies.json", "whatif.json", "model.json", "provenance.json")


@pytest.fixture(scope="module")
def exported(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("web-data")
    run("sample", out_dir=out)
    return out


def _load(path: Path, name: str):
    return json.loads((path / name).read_text(encoding="utf-8"))


def test_pipeline_and_export_are_byte_for_byte_reproducible(exported: Path, tmp_path: Path) -> None:
    run("sample", out_dir=tmp_path)
    for name in (*FILES, "manifest.json"):
        assert (exported / name).read_bytes() == (tmp_path / name).read_bytes(), name


def test_manifest_hashes_match(exported: Path) -> None:
    manifest = _load(exported, "manifest.json")
    assert manifest["schema_version"] == export_web.SCHEMA_VERSION
    assert set(manifest["files"]) == set(FILES)
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((exported / name).read_bytes()).hexdigest() == digest


def test_overview_has_every_station_with_ordered_forecasts(exported: Path) -> None:
    overview = _load(exported, "overview.json")
    assert len(overview["stations"]) == 8
    for station in overview["stations"]:
        assert station["latitude"] and station["longitude"]
        assert len(station["history"]) == export_web.HISTORY_HOURS
        assert len(station["forecast"]) == 24
        assert all(f["p10"] <= f["p50"] <= f["p90"] for f in station["forecast"])
        assert station["category_label"]
    assert overview["planner_thresholds"] == {"sensitive": 100.0, "general": 150.0}


def test_propagation_export_includes_ground_truth_for_validation(exported: Path) -> None:
    payload = _load(exported, "propagation.json")
    assert payload["links"]
    for link in payload["links"]:
        assert abs(link["lag_hours"] - link["truth_lag"]) <= 1
    episode = payload["episode"]
    assert all(len(values) == len(episode["times"]) for values in episode["aqi"].values())


def test_anomaly_export_reports_validation_and_context(exported: Path) -> None:
    payload = _load(exported, "anomalies.json")
    assert payload["validation"]["recall"] >= 0.8
    assert payload["regional_window_hours"] == max(l["lag_hours"] for l in _load(exported, "propagation.json")["links"])
    ids = {e["id"] for e in payload["events"]}
    for event in payload["events"]:
        assert event["context"] and event["drivers"]
        assert all(s["event_id"] in ids for s in event["similar"])


def test_model_export_compares_against_baselines(exported: Path) -> None:
    payload = _load(exported, "model.json")
    assert len(payload["horizons"]) == 24
    assert "upstream_anomaly" in payload["features"]
    for h in payload["horizons"]:
        assert h["mae"] < h["persistence_mae"]
        assert 0 < h["coverage"] <= 1
    assert {d["station"] for d in payload["drift"]} == {s["station"] for s in _load(exported, "overview.json")["stations"]}


def test_whatif_export_matches_the_python_reference(exported: Path) -> None:
    payload = _load(exported, "whatif.json")
    for case in payload["parity_cases"]:
        assert whatif.predict_from_payload(payload, case["inputs"]) == pytest.approx(case["expected"], abs=1e-9)


def test_provenance_marks_simulated_data(exported: Path) -> None:
    provenance = _load(exported, "provenance.json")
    assert provenance["is_simulated"] is True
    assert provenance["data_source"] == "Sample Data"
    assert provenance["stations"] == 8
    assert 0.99 <= provenance["completeness"] <= 1


def test_cli_writes_to_the_requested_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    run("sample", out_dir=tmp_path / "first")
    monkeypatch.setattr("sys.argv", ["export_web", "--out", str(tmp_path / "cli")])
    export_web.main()
    assert (tmp_path / "cli" / "manifest.json").exists()
    assert "overview.json" in capsys.readouterr().out


def test_web_whatif_fixture_matches_the_export(exported: Path) -> None:
    """The Vitest parity test reads this fixture; regenerate it when the model changes."""
    fixture = Path(__file__).resolve().parents[1] / "web" / "src" / "lib" / "fixtures" / "whatif.json"
    assert fixture.read_bytes() == (exported / "whatif.json").read_bytes(), (
        "web/src/lib/fixtures/whatif.json is stale: copy web/public/data/whatif.json over it"
    )


def test_short_history_fails_with_a_clear_error(exported: Path, tmp_path: Path) -> None:
    from src.utils import load_config, resolve_path

    cleaned = pd.read_csv(resolve_path(load_config(), "data.cleaned_file"))
    cleaned["datetime"] = pd.to_datetime(cleaned["datetime"])
    short = cleaned[cleaned["datetime"] >= cleaned["datetime"].max() - pd.Timedelta(days=3)]
    path = tmp_path / "short.csv"
    short.to_csv(path, index=False)
    with pytest.raises(export_web.InsufficientHistoryError, match="14 days"):
        export_web.export(tmp_path / "out", cleaned_path=path)


def test_non_finite_floats_are_written_as_null(tmp_path: Path) -> None:
    payload = {"drift": [{"reference_mean": float("nan"), "current_mean": 1.0}], "links": [{"r_synchronous": float("inf")}]}
    export_web._write_json(tmp_path / "x.json", payload)
    text = (tmp_path / "x.json").read_text(encoding="utf-8")
    assert "NaN" not in text and "Infinity" not in text
    assert json.loads(text) == {"drift": [{"current_mean": 1.0, "reference_mean": None}], "links": [{"r_synchronous": None}]}
