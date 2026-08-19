from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.generate_sample_data import MAX_SAMPLE_DAYS, generate_sample_aqi
from src.utils import load_config, resolve_path


def test_sample_data_can_be_generated():
    config = load_config()
    df = generate_sample_aqi(days=4)
    output = resolve_path(config, "data.sample_file")
    required = {"datetime", "site_name", "county", "aqi", "pm25", "pm10", "o3", "co", "wind_speed", "wind_directions"}

    assert output.exists()
    assert len(df) > 0
    assert required.issubset(df.columns)
    assert pd.to_datetime(df["datetime"], errors="coerce").notna().all()

    numeric = ["aqi", "pm25", "pm10", "o3", "co", "wind_speed", "wind_directions"]
    for column in numeric:
        converted = pd.to_numeric(df[column], errors="coerce")
        assert converted.notna().mean() > 0.95
    assert df[["pm25", "pm10", "o3", "co", "wind_speed"]].isna().sum().sum() > 0
    assert {"臺北市", "新北市", "高雄市"}.issubset(set(df["county"]))
    assert {"松山測站", "板橋測站", "前金測站"}.issubset(set(df["site_name"]))
    assert not {"Taipei", "Kaohsiung", "Taichung"}.intersection(set(df["site_name"].astype(str)))
    assert not {"Taipei City", "Kaohsiung City", "Taichung City"}.intersection(set(df["county"].astype(str)))


def test_sample_data_defaults_to_recent_30_days():
    df = generate_sample_aqi()
    dates = pd.to_datetime(df["datetime"])
    expected_start = date.today() - timedelta(days=29)
    assert dates.min().date() == expected_start
    assert dates.max().date() == date.today()


@pytest.mark.parametrize("days", [0, -1, MAX_SAMPLE_DAYS + 1])
def test_sample_data_rejects_invalid_day_ranges(days: int) -> None:
    with pytest.raises(ValueError, match="days must be between"):
        generate_sample_aqi(days=days)