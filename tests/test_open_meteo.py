from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
import requests

from src import fetch_open_meteo as open_meteo

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
    assert air_call["params"]["forecast_days"] == 1
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


NOW = datetime(2026, 10, 21, 12, tzinfo=ZoneInfo("Asia/Taipei"))


def _fetch_with_nulls(tmp_path: Path, edits):
    client = FakeClient()
    for location, source, field, indexes, value in edits:
        series = (client.air if source == "air" else client.weather)[location]["hourly"][field]
        for index in indexes:
            series[index] = value
    output = tmp_path / "raw" / "aqi_open_meteo.csv"
    metadata = tmp_path / "source_metadata.json"
    result = fetch_open_meteo(_config(tmp_path), output, metadata, client=client, now=NOW)
    return result, output, json.loads(metadata.read_text(encoding="utf-8"))


def test_open_meteo_trims_trailing_null_hours_and_records_them(tmp_path):
    result, output, saved = _fetch_with_nulls(tmp_path, [
        (0, "weather", "wind_speed_10m", [-3, -2, -1], None),
        (2, "air", "ozone", [-1], None),
    ])
    assert result == output
    frame = pd.read_csv(output)
    assert not frame[["aqi", "pm25", "pm10", "o3", "co", "wind_speed", "wind_directions"]].isna().any().any()
    counts = frame.groupby("site_name").size()
    full = 30 * 24 + 1
    assert counts[LOCATIONS[0]["site_name"]] == full - 3
    assert counts[LOCATIONS[2]["site_name"]] == full - 1
    assert counts[LOCATIONS[1]["site_name"]] == full
    regions = {item["name"]: item for item in saved["missing_values"]["regions"]}
    assert regions[LOCATIONS[0]["site_name"]]["trimmed_trailing_hours"] == 3
    assert regions[LOCATIONS[2]["site_name"]]["trimmed_trailing_hours"] == 1
    assert regions[LOCATIONS[1]["site_name"]] == {"name": LOCATIONS[1]["site_name"], "trimmed_trailing_hours": 0, "masked_values": {}}
    assert saved["row_count"] == len(frame)


def test_open_meteo_keeps_isolated_interior_null_for_short_gap_filling(tmp_path):
    from src.analytics.panel import build_panels

    result, output, saved = _fetch_with_nulls(tmp_path, [(1, "air", "us_aqi", [100], None)])
    assert result == output
    frame = pd.read_csv(output)
    site = LOCATIONS[1]["site_name"]
    assert int(frame["aqi"].isna().sum()) == 1
    assert frame.loc[frame["aqi"].isna(), "site_name"].tolist() == [site]
    regions = {item["name"]: item for item in saved["missing_values"]["regions"]}
    assert regions[site]["masked_values"] == {"us_aqi": 1}
    assert regions[site]["trimmed_trailing_hours"] == 0
    assert saved["missing_values"]["max_null_run_hours"] == 3
    assert not build_panels(frame)["aqi"][site].isna().any()


def test_open_meteo_fails_closed_on_long_or_frequent_null_runs(tmp_path):
    long_gap = [(0, "air", "pm10", range(200, 204), None)]
    frequent = [(3, "weather", "wind_direction_10m", range(10, 700, 40), None)]
    for case, edits in (("long", long_gap), ("frequent", frequent)):
        result, output, saved = _fetch_with_nulls(tmp_path / case, edits)
        assert result is None
        assert not output.exists()
        assert saved["status"] == "fallback"


def test_open_meteo_still_rejects_non_numeric_values(tmp_path):
    for case, value in (("text", "n/a"), ("bool", True), ("nan", "NaN")):
        result, output, saved = _fetch_with_nulls(tmp_path / case, [(0, "air", "pm2_5", [50], value)])
        assert result is None
        assert not output.exists()
        assert saved["status"] == "fallback"


def test_open_meteo_requests_today_and_keeps_only_started_hours(tmp_path):
    """The archive must reach the current hour, or the 24-hour forecast starts at
    yesterday 23:00 and is mostly in the past by the time the daily build runs."""
    client = FakeClient()
    # Like the live API with forecast_days=1: the series runs to 23:00 of the current day.
    end = pd.Timestamp("2026-10-21T23:00:00+08:00")
    extra = pd.date_range(pd.Timestamp(client.air[0]["hourly"]["time"][-1]) + pd.Timedelta(hours=1), end, freq="h")
    for item in (*client.air, *client.weather):
        hourly = item["hourly"]
        hourly["time"] += [stamp.isoformat(timespec="minutes") for stamp in extra]
        for key, values in hourly.items():
            if key != "time":
                values += [values[-1]] * len(extra)
    now = datetime(2026, 10, 21, 20, 25, tzinfo=ZoneInfo("Asia/Taipei"))
    output = tmp_path / "raw" / "aqi_open_meteo.csv"
    metadata = tmp_path / "source_metadata.json"
    result = fetch_open_meteo(_config(tmp_path), output, metadata, client=client, now=now)

    assert result == output
    for _, call in client.calls:
        assert call["params"]["forecast_days"] == 1
    frame = pd.read_csv(output)
    assert set(frame.groupby("site_name")["datetime"].max()) == {"2026-10-21T20:00+08:00"}
    saved = json.loads(metadata.read_text(encoding="utf-8"))
    assert saved["datetime_range"]["max"] == "2026-10-21T12:00:00Z"  # 20:00 Asia/Taipei


@pytest.mark.parametrize("failure", ["timeout", "stream", "503", "exhausted", "redirect", "tls", "invalid-json"])
def test_open_meteo_request_retry_boundary(monkeypatch, failure):
    responses = []
    waits = []
    calls = []

    class BrokenStream(FakeResponse):
        def iter_content(self, chunk_size):
            yield b'{"partial":'
            raise requests.exceptions.ChunkedEncodingError("truncated")

    class Client:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            if failure == "exhausted" or (failure == "timeout" and len(calls) == 1):
                raise requests.exceptions.ReadTimeout("timed out")
            if failure == "tls":
                raise requests.exceptions.SSLError("bad certificate")
            if len(calls) == 1 and failure == "stream":
                response = BrokenStream({}, url=url)
            elif len(calls) == 1 and failure == "503":
                response = FakeResponse({}, url=url, status=503)
            elif failure == "redirect":
                response = FakeResponse({}, url=url, status=302)
            else:
                response = FakeResponse({"complete": True}, url=url)
                if failure == "invalid-json":
                    response.content = b"{"
            responses.append(response)
            return response

    monkeypatch.setattr(open_meteo, "sleep", waits.append)
    if failure == "exhausted":
        with pytest.raises(requests.exceptions.ReadTimeout):
            open_meteo._get_json(Client(), WEATHER_URL, {})
        assert waits == [1, 2]
        assert len(calls) == 3
    elif failure in {"redirect", "tls", "invalid-json"}:
        with pytest.raises((ValueError, requests.exceptions.SSLError)):
            open_meteo._get_json(Client(), WEATHER_URL, {})
        assert waits == []
        assert len(calls) == 1
    else:
        assert open_meteo._get_json(Client(), WEATHER_URL, {}) == {"complete": True}
        assert waits == [1]
        assert len(calls) == 2
    assert all(response.closed for response in responses)
    assert all(call["allow_redirects"] is False for _, call in calls)
    assert all(call["timeout"] == (12, 40) for _, call in calls)
