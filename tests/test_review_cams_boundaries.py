from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.fetch_open_meteo import fetch_open_meteo
from tests.test_open_meteo import FakeClient, _config


@pytest.mark.parametrize("gap", ["stale_tail", "interior_hour"])
def test_weather_alignment_failure_preserves_the_verified_snapshot(tmp_path, gap):
    client = FakeClient()
    for item in client.weather:
        hourly = item["hourly"]
        if gap == "stale_tail":
            # Air source is fresh, but the matched weather series ends 10 days earlier.
            for key in hourly:
                hourly[key] = hourly[key][:-240]
        else:
            for key in hourly:
                del hourly[key][400]
    output = tmp_path / "previous.csv"
    metadata = tmp_path / "source_metadata.json"
    output.write_text("previous verified snapshot", encoding="utf-8")
    result = fetch_open_meteo(
        _config(tmp_path), output, metadata, client=client,
        now=datetime(2026, 10, 21, 12, tzinfo=ZoneInfo("Asia/Taipei")),
    )
    assert result is None
    assert output.read_text(encoding="utf-8") == "previous verified snapshot"
    assert json.loads(metadata.read_text(encoding="utf-8"))["status"] == "fallback"


@pytest.mark.parametrize("source,field", [
    ("air", "us_aqi"), ("air", "pm2_5"), ("air", "ozone"),
    ("weather", "wind_speed_10m"), ("weather", "wind_direction_10m"),
])
def test_model_measurements_must_not_accept_json_booleans(tmp_path, source, field):
    client = FakeClient()
    items = client.air if source == "air" else client.weather
    items[0]["hourly"][field][400] = True
    output = tmp_path / "model.csv"
    result = fetch_open_meteo(
        _config(tmp_path), output, tmp_path / "metadata.json", client=client,
        now=datetime(2026, 10, 21, 12, tzinfo=ZoneInfo("Asia/Taipei")),
    )
    assert result is None
    assert not output.exists()
