from __future__ import annotations

import pandas as pd
import pytest

from src import evaluate, features, preprocess
from src.source_metadata import file_sha256


def input_frame():
    rows = []
    for site, county in (("A", "臺北市"), ("B", "臺中市")):
        for hour in range(20):
            rows.append({"site_name": site, "county": county, "datetime": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=hour),
                         "aqi": 40. + hour, "pm25": 10., "pm10": 20., "o3": 30., "co": .3, "wind_speed": 2., "wind_directions": 90.})
    return pd.DataFrame(rows)


def test_api_label_requires_metadata_bound_to_selected_file(monkeypatch, tmp_path):
    path = tmp_path / "sample.csv"
    input_frame().to_csv(path, index=False)
    monkeypatch.setattr(preprocess, "_input_path", lambda config, mode: path)
    monkeypatch.setattr(preprocess, "load_source_metadata", lambda config: {})
    monkeypatch.setattr(preprocess, "write_csv", lambda *args, **kwargs: None)
    assert preprocess.preprocess(mode="api")["data_source"].eq("Sample Data").all()
    metadata = {"status": "success", "data_source": "API Data", "is_simulated_data": False, "data_file_sha256": file_sha256(path)}
    assert preprocess.preprocess(mode="api", input_path=path, source_metadata=metadata)["data_source"].eq("API Data").all()
    metadata["data_file_sha256"] = "0" * 64
    assert preprocess.preprocess(mode="api", input_path=path, source_metadata=metadata)["data_source"].eq("Sample Data").all()


def test_missing_identity_and_long_gap_are_not_silently_filled(monkeypatch, tmp_path):
    frame = input_frame()
    frame.loc[0, "site_name"] = None
    frame.loc[1, "county"] = " "
    frame.loc[frame["site_name"].eq("A") & frame["datetime"].ge("2026-01-01 10:00"), "aqi"] = None
    path = tmp_path / "dirty.csv"
    frame.to_csv(path, index=False)
    monkeypatch.setattr(preprocess, "write_csv", lambda *args, **kwargs: None)
    cleaned = preprocess.preprocess(input_path=path, source_metadata={})
    assert cleaned["site_name"].notna().all()
    assert cleaned["county"].str.strip().ne("").all()
    a = cleaned.loc[cleaned["site_name"].eq("A")]
    assert a["datetime"].max() == pd.Timestamp("2026-01-01 12:00")


def test_hour_named_features_restart_after_missing_hour(monkeypatch, tmp_path):
    frame = input_frame()
    frame = frame.loc[~(frame["site_name"].eq("A") & frame["datetime"].eq("2026-01-01 08:00"))]
    cleaned_path = tmp_path / "cleaned.csv"
    output_path = tmp_path / "features.csv"
    frame.to_csv(cleaned_path, index=False)
    original_resolve = features.resolve_path

    def resolve_test_path(config, key):
        return {"data.cleaned_file": cleaned_path, "data.features_file": output_path}.get(key) or original_resolve(config, key)

    monkeypatch.setattr(features, "resolve_path", resolve_test_path)
    result = features.build_features()
    a = result.loc[result["site_name"].eq("A")]
    assert not a["datetime"].isin(pd.to_datetime(["2026-01-01 09:00", "2026-01-01 10:00", "2026-01-01 11:00"])).any()
    assert a.loc[a["datetime"].eq("2026-01-01 12:00"), "lag_3_aqi"].tolist() == [49.]
    assert output_path.exists()


def test_double_renderer_failure_is_reported(monkeypatch, tmp_path):
    # Empty frames fail primary rendering; fallback also leaves a partial file.
    names = ("aqi_trend.png", "prediction_vs_actual.png", "anomaly_cases.png")
    for name in names:
        (tmp_path / name).write_bytes(b"previous-run")
    unrelated = tmp_path / "user-notes.txt"
    unrelated.write_text("keep", encoding="utf-8")

    def fail(*args, **kwargs):
        (tmp_path / "aqi_trend.png").write_bytes(b"partial-new-run")
        raise ValueError("forced fallback failure")
    monkeypatch.setattr(evaluate, "_plot_fallback_figures", fail)
    with pytest.raises(RuntimeError, match="both renderers"):
        evaluate._plot_figures(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), tmp_path)
    assert not list(tmp_path.glob("*.png"))
    assert unrelated.read_text(encoding="utf-8") == "keep"
