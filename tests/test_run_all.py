from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_all import run
from src.utils import load_config, resolve_path


def test_run_all_sample_creates_required_outputs():
    config = load_config()
    assert (ROOT / "run_all.py").exists()
    assert (ROOT / "run_project.bat").exists()
    assert (ROOT / "run_project_bat內容.txt").exists()
    assert (ROOT / "run_project.bat").read_text(encoding="utf-8") == (
        ROOT / "run_project_bat內容.txt"
    ).read_text(encoding="utf-8")

    outputs = run("sample")
    assert outputs

    required = [
        resolve_path(config, "data.sample_file"),
        resolve_path(config, "data.cleaned_file"),
        resolve_path(config, "data.features_file"),
        resolve_path(config, "data.predictions_file"),
        resolve_path(config, "data.anomaly_file"),
        resolve_path(config, "models.predictor"),
        resolve_path(config, "models.anomaly_detector"),
        resolve_path(config, "reports.metrics_dir") / "evaluation_summary.json",
    ]
    for path in required:
        assert path.exists()
        assert path.stat().st_size > 0
