from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.fetch_open_meteo import AIR_URL, LOCATIONS, PROVIDER, WEATHER_URL, fetch_open_meteo


class FakeResponse:
    def __init__(self, payload, *, url: str, status: int = 200):
        self.content = json.dumps(payload).encode("utf-8")
        self.headers = {"content-length": str(len(self.content))}
        self.url, self.status_code, self.closed = url, status, False

    def iter_content(self, chunk_size: int):
        yield self.content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def close(self):
        self.closed = True


def _payloads(duplicate_grid: bool = False, step_hours: int = 1):
    air_times = pd.date_range("2026-09-20T00:00:00+08:00", periods=(30 * 24) // step_hours + 1, freq=f"{step_hours}h")
    weather_times = pd.date_range(air_times[0], air_times[-1], freq="h")
    air = []
    weather = []
    for index, place in enumerate(LOCATIONS):
        latitude = place["latitude"]
        longitude = place["longitude"]
        if duplicate_grid and index == 1:
            latitude, longitude = LOCATIONS[0]["latitude"], LOCATIONS[0]["longitude"]
        air.append({
            "latitude": latitude, "longitude": longitude,
            "hourly": {
                "time": [stamp.isoformat(timespec="minutes") for stamp in air_times],
                "us_aqi": [35 + index] * len(air_times),
                "pm2_5": [5.0] * len(air_times),
                "pm10": [10.0] * len(air_times),
                "ozone": [40.0] * len(air_times),
                "carbon_monoxide": [180.0] * len(air_times),
            },
        })
        weather.append({
            "latitude": latitude, "longitude": longitude,
            "hourly": {
                "time": [stamp.isoformat(timespec="minutes") for stamp in weather_times],
                "wind_speed_10m": [1.5] * len(weather_times),
                "wind_direction_10m": [90] * len(weather_times),
            },
        })
    return air, weather


class FakeClient:
    def __init__(self, *, duplicate_grid: bool = False, redirect: bool = False, step_hours: int = 1):
        self.air, self.weather = _payloads(duplicate_grid, step_hours)
        self.redirect = redirect
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.redirect:
            return FakeResponse({}, url="https://evil.example/steal", status=302)
        return FakeResponse(self.air if url == AIR_URL else self.weather, url=url)


def _config(tmp_path: Path):
    return {
        "api": {"past_days": 60, "minimum_history_days": 14},
        "data": {"raw_dir": str(tmp_path / "raw")},
    }


def test_open_meteo_snapshot_is_unregistered_model_data_with_grid_metadata(tmp_path):
    client = FakeClient()
    now = datetime(2026, 10, 21, 12, tzinfo=ZoneInfo("Asia/Taipei"))
    output = tmp_path / "raw" / "aqi_open_meteo.csv"
    metadata = tmp_path / "source_metadata.json"
    result = fetch_open_meteo(_config(tmp_path), output, metadata, client=client, now=now)

    assert result == output
    assert len(client.calls) == 2
    air_url, air_call = client.calls[0]
    weather_url, weather_call = client.calls[1]
    assert air_url == AIR_URL and weather_url == WEATHER_URL
    assert air_call["allow_redirects"] is False and weather_call["allow_redirects"] is False
    assert weather_call["params"]["wind_speed_unit"] == "ms"
    assert air_call["params"]["domains"] == "cams_global"
    assert air_call["params"]["past_days"] == 60
    assert air_call["params"]["forecast_days"] == 0
    assert "apikey" not in air_call["params"] and "api_key" not in air_call["params"]
    frame = pd.read_csv(output)
    assert frame["site_name"].nunique() == len(LOCATIONS)
    assert frame["latitude"].nunique() == len(LOCATIONS)
    assert frame["coordinate_source"].str.contains("CAMS global grid").all()
    saved = json.loads(metadata.read_text(encoding="utf-8"))
    assert saved["provider"] == PROVIDER
    assert saved["data_source"] == "Model Estimate"
    assert saved["is_simulated_data"] is False
    assert saved["native_temporal_resolution_hours"] == 3
    assert saved["api_output_temporal_resolution_hours"] == 1
    assert saved["spatial_resolution_km"] == 45
    assert saved["aqi_standard"] == "U.S. EPA AQI"


def test_open_meteo_rejects_redirect_and_preserves_previous_snapshot(tmp_path):
    output = tmp_path / "raw" / "aqi_open_meteo.csv"
    output.parent.mkdir()
    output.write_text("previous verified snapshot", encoding="utf-8")
    metadata = tmp_path / "source_metadata.json"
    result = fetch_open_meteo(
        _config(tmp_path), output, metadata, client=FakeClient(redirect=True),
        now=datetime(2026, 10, 21, 12, tzinfo=ZoneInfo("Asia/Taipei")),
    )
    assert result is None
    assert output.read_text(encoding="utf-8") == "previous verified snapshot"
    saved = json.loads(metadata.read_text(encoding="utf-8"))
    assert saved["status"] == "fallback"
    assert "evil.example" not in json.dumps(saved)


def test_open_meteo_rejects_non_hourly_api_output(tmp_path):
    output = tmp_path / "raw" / "aqi_open_meteo.csv"
    metadata = tmp_path / "source_metadata.json"
    result = fetch_open_meteo(
        _config(tmp_path), output, metadata, client=FakeClient(step_hours=2),
        now=datetime(2026, 10, 21, 12, tzinfo=ZoneInfo("Asia/Taipei")),
    )
    assert result is None
    assert not output.exists()


def test_open_meteo_rejects_aliased_grid_cells_without_publication(tmp_path):
    output = tmp_path / "raw" / "aqi_open_meteo.csv"
    metadata = tmp_path / "source_metadata.json"
    result = fetch_open_meteo(
        _config(tmp_path), output, metadata, client=FakeClient(duplicate_grid=True),
        now=datetime(2026, 10, 21, 12, tzinfo=ZoneInfo("Asia/Taipei")),
    )
    assert result is None
    assert not output.exists()
