from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.features import build_features
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
