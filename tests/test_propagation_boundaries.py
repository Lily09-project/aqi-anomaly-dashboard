from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.export_web import build_propagation


def test_constant_station_series_export_an_explicit_empty_episode():
    index = pd.date_range("2026-01-01", periods=15 * 24, freq="h")
    pm25 = pd.DataFrame({"A": np.full(len(index), 10.0), "B": np.full(len(index), 20.0)}, index=index)
    payload, upstream = build_propagation({"pm25": pm25, "aqi": pm25 * 2}, None)
    assert upstream == {}
    assert payload["links"] == []
    assert payload["episode"] == {
        "start": None, "end": None, "times": [], "aqi": {"A": [], "B": []},
    }
    # Missing variation is unavailable analysis, never a NaN JSON token or an invented plume.
    json.dumps(payload, allow_nan=False)
