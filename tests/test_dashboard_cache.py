from __future__ import annotations

import pandas as pd
import pytest

import src.dashboard.data_service as data_service
from src.dashboard.data_service import (
    clear_artifact_cache,
    read_csv_versioned,
    read_json_versioned,
)


def test_unchanged_csv_is_read_once(monkeypatch, tmp_path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("value\n1\n", encoding="utf-8")
    calls = 0
    original = pd.read_csv

    def counted_read(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", counted_read)
    clear_artifact_cache()

    first = read_csv_versioned(path)
    second = read_csv_versioned(path)

    assert calls == 1
    assert first.equals(second)
    assert first is not second


def test_csv_change_invalidates_cache(monkeypatch, tmp_path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("value\n1\n", encoding="utf-8")
    calls = 0
    original = pd.read_csv

    def counted_read(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", counted_read)
    clear_artifact_cache()
    read_csv_versioned(path)
    path.write_text("value\n1\n2\n", encoding="utf-8")

    changed = read_csv_versioned(path)

    assert calls == 2
    assert changed["value"].tolist() == [1, 2]


def test_missing_csv_returns_empty_frame(tmp_path) -> None:
    clear_artifact_cache()
    assert read_csv_versioned(tmp_path / "missing.csv").empty


def test_malformed_existing_csv_reports_actionable_error(tmp_path) -> None:
    path = tmp_path / "broken.csv"
    path.write_text('value\n"unterminated\n', encoding="utf-8")
    clear_artifact_cache()

    assert hasattr(data_service, "ArtifactReadError")
    with pytest.raises(data_service.ArtifactReadError, match=r"broken\.csv.*run_all\.py --mode sample"):
        read_csv_versioned(path)


def test_malformed_existing_json_reports_actionable_error(tmp_path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"status":', encoding="utf-8")
    clear_artifact_cache()

    assert hasattr(data_service, "ArtifactReadError")
    with pytest.raises(data_service.ArtifactReadError, match=r"broken\.json.*run_all\.py --mode sample"):
        read_json_versioned(path)
def test_existing_csv_with_missing_required_columns_reports_artifact_error(tmp_path) -> None:
    path = tmp_path / "wrong-schema.csv"
    path.write_text("foo\n1\n", encoding="utf-8")
    clear_artifact_cache()

    with pytest.raises(data_service.ArtifactReadError, match=r"wrong-schema\.csv.*格式錯誤"):
        read_csv_versioned(path, required_columns=("datetime", "aqi", "pm25"))
