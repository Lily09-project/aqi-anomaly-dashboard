from __future__ import annotations

import json
import py_compile
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app_helpers import to_chinese_location_name, to_chinese_site_name
from src.theme import DEFAULT_THEME_NAME, REQUIRED_THEME_KEYS, THEME, THEME_OPTIONS, validate_theme_contrast
from src.utils import load_config, load_model, project_path, resolve_path


def _hex_to_rgb(color: str) -> tuple[float, float, float]:
    color = color.strip().lstrip("#")
    return tuple(int(color[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _relative_luminance(color: str) -> float:
    channels = []
    for channel in _hex_to_rgb(color):
        channels.append(channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(foreground: str, background: str) -> float:
    fg = _relative_luminance(foreground)
    bg = _relative_luminance(background)
    lighter, darker = max(fg, bg), min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def _assert_file(config: dict, dotted_key: str) -> None:
    path = resolve_path(config, dotted_key)
    assert path.exists(), f"Missing file: {path}"
    assert path.stat().st_size > 0, f"Empty file: {path}"


def run_smoke_test() -> None:
    config = load_config()
    required_dirs = ["data/sample", "data/processed", "models", "reports/metrics", "reports/figures", "src", "tests"]
    for rel in required_dirs:
        assert project_path(rel).exists(), f"Missing directory: {rel}"

    app_path = project_path("app.py")
    assert app_path.exists(), "Missing app.py"
    py_compile.compile(str(app_path), doraise=True)

    bat_path = project_path("run_project.bat")
    bat_text_path = project_path("run_project_bat內容.txt")
    assert bat_path.exists(), "Missing run_project.bat"
    assert bat_text_path.exists(), "Missing run_project_bat內容.txt"
    assert bat_path.read_text(encoding="utf-8") == bat_text_path.read_text(
        encoding="utf-8"
    ), "run_project.bat and run_project_bat內容.txt are not identical"

    for key in [
        "data.cleaned_file",
        "data.features_file",
        "data.predictions_file",
        "data.anomaly_file",
        "data.events_file",
        "models.predictor",
        "models.anomaly_detector",
        "reports.metrics_dir",
    ]:
        if key == "reports.metrics_dir":
            summary = resolve_path(config, key) / "evaluation_summary.json"
            assert summary.exists() and summary.stat().st_size > 0, f"Missing summary: {summary}"
            for report_name in ["backtest_metrics.json", "data_health.json"]:
                report = resolve_path(config, key) / report_name
                assert report.exists() and report.stat().st_size > 0, f"Missing report: {report}"
        else:
            _assert_file(config, key)

    features = pd.read_csv(resolve_path(config, "data.features_file"))
    assert len(features) > 0, "Feature data has no rows"
    required = set(config["train"]["feature_columns"] + ["target_next_hour_aqi", "target_aqi"])
    assert required.issubset(features.columns), f"Missing feature columns: {required - set(features.columns)}"
    assert features[list(required)].isna().sum().sum() == 0, "Feature data contains missing modeling values"
    assert {"county_display", "site_name_display"}.issubset(features.columns), "Missing display columns"

    predictions = pd.read_csv(resolve_path(config, "data.predictions_file"))
    anomalies = pd.read_csv(resolve_path(config, "data.anomaly_file"))
    events = pd.read_csv(resolve_path(config, "data.events_file"))
    assert {"county_display", "site_name_display"}.issubset(predictions.columns), "Predictions missing display columns"
    assert {"county_display", "site_name_display"}.issubset(anomalies.columns), "Anomaly results missing display columns"
    assert {"event_id", "duration_hours", "peak_aqi", "evidence_summary"}.issubset(events.columns), "Events missing investigation columns"
    assert "Taipei" not in set(features["site_name_display"].astype(str)), "English site name leaked to display column"
    assert to_chinese_location_name("Taipei") == "臺北市"
    assert to_chinese_site_name("Taipei") == "松山測站"
    assert to_chinese_location_name("") == "未知地區"

    required_theme_keys = {"primary", "background", "card", "text", "muted_text", "accent", "danger"}
    assert required_theme_keys.issubset(THEME), f"Missing theme keys: {required_theme_keys - set(THEME)}"
    assert THEME["card"].lower() != THEME["text"].lower(), "Card and text colors must differ"
    assert DEFAULT_THEME_NAME in THEME_OPTIONS, "Default theme is not registered"
    for theme_name, theme in THEME_OPTIONS.items():
        missing_theme_keys = REQUIRED_THEME_KEYS - set(theme)
        assert not missing_theme_keys, f"{theme_name} missing theme keys: {missing_theme_keys}"
        contrast = validate_theme_contrast(theme)
        assert contrast["passed"], f"{theme_name} contrast failed: {contrast}"

    summary_path = resolve_path(config, "reports.metrics_dir") / "evaluation_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "data_health" in summary and "backtest_metrics" in summary, "Evaluation summary missing reliability reports"
    load_model(resolve_path(config, "models.predictor"))
    load_model(resolve_path(config, "models.anomaly_detector"))

    import app

    assert hasattr(app, "DISPLAY_COLUMN_MAP"), "app.py must expose DISPLAY_COLUMN_MAP"


def main() -> None:
    run_smoke_test()
    print("Smoke test passed.")


if __name__ == "__main__":
    main()
