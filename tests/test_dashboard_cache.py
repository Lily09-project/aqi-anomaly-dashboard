from __future__ import annotations

import pandas as pd

from src.dashboard.data_service import clear_artifact_cache, read_csv_versioned


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
