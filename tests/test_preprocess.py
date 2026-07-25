from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.app_helpers import to_chinese_location_name
from src.generate_sample_data import generate_sample_aqi
from src.preprocess import normalize_columns, preprocess
from src.utils import load_config, resolve_path


def test_preprocess_outputs_cleaned_data():
    config = load_config()
    generate_sample_aqi(days=4)
    cleaned = preprocess(mode="sample")
    output = resolve_path(config, "data.cleaned_file")

    assert output.exists()
    assert len(cleaned) > 0
    assert pd.api.types.is_datetime64_any_dtype(cleaned["datetime"])
    for column in ["aqi", "pm25", "pm10", "o3", "co", "wind_speed"]:
        assert pd.api.types.is_numeric_dtype(cleaned[column])
        assert cleaned[column].notna().all()
    assert {"county_display", "site_name_display"}.issubset(cleaned.columns)
    assert cleaned["county_display"].notna().all()
    assert cleaned["site_name_display"].notna().all()


def test_alias_mapping_handles_api_field_variants(tmp_path):
    alias_df = pd.DataFrame(
        {
            "DataCreationDate": ["2026-01-01 00:00", "2026-01-01 01:00"],
            "SiteName": ["Taipei", "Taipei"],
            "County": ["Taipei City", "Taipei City"],
            "AQI": ["42", "48"],
            "PM2.5": ["12", "15"],
            "PM10": ["30", "33"],
            "O3": ["18", "20"],
            "CO": ["0.3", "0.4"],
            "WindSpeed": ["2.5", "2.9"],
            "WindDirec": ["120", "130"],
        }
    )
    normalized = normalize_columns(alias_df)
    assert {"datetime", "site_name", "aqi", "pm25"}.issubset(normalized.columns)

    csv_path = tmp_path / "api_alias.csv"
    alias_df.to_csv(csv_path, index=False)
    cleaned = preprocess(mode="api", input_path=csv_path)
    assert cleaned["aqi"].tolist() == [42, 48]
    assert cleaned["pm25"].tolist() == [12, 15]
    assert cleaned["county"].tolist() == ["Taipei City", "Taipei City"]
    assert cleaned["county_display"].tolist() == ["臺北市", "臺北市"]
    assert cleaned["site_name_display"].tolist() == ["松山測站", "松山測站"]
    assert to_chinese_location_name("Kaohsiung") == "高雄市"


def test_preprocess_handles_mixed_missing_tokens(tmp_path):
    dirty_df = pd.DataFrame(
        {
            "datetime": ["2026-01-01 00:00", "2026-01-01 01:00", "2026-01-01 02:00"],
            "site_name": ["Taipei", "Taipei", "Taipei"],
            "county": ["Taipei City", "Taipei City", "Taipei City"],
            "aqi": ["42", "ND", "50"],
            "pm25": ["12", "NA", "16"],
            "pm10": ["-", "33", "35"],
            "o3": ["18", "x", "22"],
            "co": ["0.3", "", "0.4"],
            "wind_speed": ["2.5", "2.9", "NA"],
            "wind_directions": ["120", "130", "140"],
        }
    )
    csv_path = tmp_path / "dirty.csv"
    dirty_df.to_csv(csv_path, index=False)
    cleaned = preprocess(mode="api", input_path=csv_path)
    assert cleaned[["aqi", "pm25", "pm10", "o3", "co", "wind_speed"]].isna().sum().sum() == 0
    assert {"county_display", "site_name_display"}.issubset(cleaned.columns)


def test_preprocess_does_not_fill_from_future_values(tmp_path):
    rows = pd.DataFrame(
        {
            "datetime": ["2026-06-01 00:00", "2026-06-01 01:00", "2026-06-01 02:00"],
            "site_name": ["測試站"] * 3,
            "county": ["測試縣市"] * 3,
            "aqi": [None, 40, 45],
            "pm25": [10, 11, 12],
            "pm10": [20, 21, 22],
            "o3": [30, 31, 32],
            "co": [0.3, 0.3, 0.4],
            "wind_speed": [2.0, 2.1, 2.2],
            "wind_directions": [90, 100, 110],
        }
    )
    csv_path = tmp_path / "causal_missing.csv"
    rows.to_csv(csv_path, index=False)
    cleaned = preprocess(mode="api", input_path=csv_path)

    assert cleaned["datetime"].min() == pd.Timestamp("2026-06-01 01:00")
    assert cleaned["data_source"].eq("API Data").all()
