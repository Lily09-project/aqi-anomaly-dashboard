from __future__ import annotations

import json

import pandas as pd
import pytest

from src.utils import _atomic_write, write_csv, write_json


def test_artifact_writers_are_atomic_and_create_parent(tmp_path) -> None:
    csv_path = tmp_path / "nested" / "data.csv"
    json_path = tmp_path / "nested" / "metrics.json"

    write_csv(pd.DataFrame({"value": [1, 2]}), csv_path, index=False)
    write_json(json_path, {"rows": 2})

    assert pd.read_csv(csv_path)["value"].tolist() == [1, 2]
    assert json.loads(json_path.read_text(encoding="utf-8")) == {"rows": 2}
    assert list(csv_path.parent.glob(".*.tmp")) == []


def test_atomic_writer_cleans_up_after_failure(tmp_path) -> None:
    target = tmp_path / "artifact.json"

    def fail_writer(temporary_path) -> None:
        temporary_path.write_text("partial", encoding="utf-8")
        raise RuntimeError("simulated writer failure")

    with pytest.raises(RuntimeError):
        _atomic_write(target, fail_writer)

    assert not target.exists()
    assert list(tmp_path.glob(".*.tmp")) == []