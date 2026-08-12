from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features import build_features, historical_station_hour_baseline
from src.generate_sample_data import generate_sample_aqi
from src.preprocess import preprocess
from src.utils import load_config, resolve_path


def test_features_are_created_without_cross_site_leakage():
    config = load_config()
    generate_sample_aqi(days=5)
    preprocess(mode="sample")
    features = build_features()

    expected = {
        "hour",
        "day_of_week",
        "month",
        "is_weekend",
        "lag_1_aqi",
        "lag_3_aqi",
        "rolling_3h_aqi",
        "rolling_6h_aqi",
        "rolling_12h_aqi",
        "target_next_hour_aqi",
        "target_aqi",
    }
    assert resolve_path(config, "data.features_file").exists()
    assert len(features) > 0
    assert expected.issubset(features.columns)
    assert {"county_display", "site_name_display"}.issubset(features.columns)
    assert features[config["train"]["feature_columns"] + ["target_next_hour_aqi"]].isna().sum().sum() == 0

    for site, group in features.groupby("site_name"):
        assert (group["site_name"] == site).all()
        assert group["datetime"].is_monotonic_increasing
        assert group["site_name_display"].nunique() == 1


def test_target_aqi_is_next_hour_same_station_and_not_a_feature():
    config = load_config()
    generate_sample_aqi(days=4, start_date="2026-06-01")
    preprocess(mode="sample")
    features = build_features()

    assert "target_aqi" not in config["train"]["feature_columns"]
    assert "target_next_hour_aqi" not in config["train"]["feature_columns"]

    for _, group in features.groupby("site_name"):
        group = group.sort_values("datetime").reset_index(drop=True)
        assert (group["target_aqi"] == group["target_next_hour_aqi"]).all()

        lookup = group.set_index("datetime")["aqi"]
        for _, row in group.head(20).iterrows():
            next_hour = row["datetime"] + __import__("pandas").Timedelta(hours=1)
            if next_hour in lookup.index:
                assert row["target_aqi"] == lookup.loc[next_hour]


def test_lag_and_rolling_features_only_use_past_same_station_values():
    generate_sample_aqi(days=4, start_date="2026-06-01")
    cleaned = preprocess(mode="sample")
    features = build_features()

    for site, group in features.groupby("site_name"):
        source = cleaned[cleaned["site_name"] == site].set_index("datetime").sort_index()
        assert group["datetime"].min() >= source.index.min() + pd.Timedelta(hours=3)
        for _, row in group.head(24).iterrows():
            timestamp = row["datetime"]
            assert row["lag_1_aqi"] == source.loc[timestamp - pd.Timedelta(hours=1), "aqi"]
            assert row["lag_3_aqi"] == source.loc[timestamp - pd.Timedelta(hours=3), "aqi"]
            expected = source.loc[
                timestamp - pd.Timedelta(hours=3) : timestamp - pd.Timedelta(hours=1), "aqi"
            ].mean()
            assert math.isclose(row["rolling_3h_aqi"], expected, rel_tol=1e-9, abs_tol=1e-9)


def test_historical_station_hour_baseline_uses_only_earlier_timestamps() -> None:
    frame = pd.DataFrame(
        {
            "datetime": pd.to_datetime([
                "2026-06-01 10:00", "2026-06-01 10:00",
                "2026-06-02 10:00", "2026-06-02 10:00",
                "2026-06-03 10:00", "2026-06-03 10:00",
            ]),
            "site_name": ["A", "B"] * 3,
            "aqi": [10.0, 100.0, 20.0, 200.0, 30.0, 300.0],
        }
    )
    original = historical_station_hour_baseline(frame)
    changed = frame.copy()
    changed.loc[4:, "aqi"] = [999.0, 888.0]
    mutated = historical_station_hour_baseline(changed)

    pd.testing.assert_series_equal(original.iloc[:4], mutated.iloc[:4])
    assert math.isnan(original.iloc[0])
    assert math.isnan(original.iloc[1])
    assert original.iloc[2] == 10.0
    assert original.iloc[3] == 100.0
    assert original.iloc[4] == 15.0
    assert original.iloc[5] == 150.0


def test_historical_station_hour_baseline_falls_back_station_then_global() -> None:
    frame = pd.DataFrame(
        {
            "datetime": pd.to_datetime([
                "2026-06-01 09:00",
                "2026-06-01 10:00",
                "2026-06-01 11:00",
            ]),
            "site_name": ["A", "A", "B"],
            "aqi": [40.0, 60.0, 80.0],
        }
    )
    baseline = historical_station_hour_baseline(frame)

    assert math.isnan(baseline.iloc[0])
    assert baseline.iloc[1] == 40.0
    assert baseline.iloc[2] == 50.0