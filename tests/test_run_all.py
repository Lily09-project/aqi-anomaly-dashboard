from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_all import run  # noqa: E402
from src.utils import load_config, resolve_path  # noqa: E402


def test_run_all_sample_creates_data_ground_truth_and_web_export(tmp_path: Path) -> None:
    config = load_config()
    hashes = run("sample", out_dir=tmp_path)

    assert set(hashes) == {"overview.json", "propagation.json", "anomalies.json", "whatif.json", "model.json", "provenance.json"}
    for path in (
        resolve_path(config, "data.sample_file"),
        resolve_path(config, "data.sample_file").with_name("injected_events.csv"),
        resolve_path(config, "data.cleaned_file"),
        tmp_path / "manifest.json",
    ):
        assert path.exists() and path.stat().st_size > 0, path

    cleaned = pd.read_csv(resolve_path(config, "data.cleaned_file"))
    assert (cleaned["data_source"] == "Sample Data").all()
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"] == hashes
