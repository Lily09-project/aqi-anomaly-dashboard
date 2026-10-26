from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.analytics import forecast, whatif
from src.analytics.panel import build_panels
from src.export_web import training_upstream


def frames():
    rng = np.random.default_rng(32)
    times = pd.date_range("2026-01-01", periods=30*24, freq="h")
    signal = 60 + 10*np.sin(np.arange(len(times))/10) + rng.normal(size=len(times))
    rows = []
    for station, shift in [("A", 0), ("B", 3)]:
        series = np.roll(signal, shift)
        for stamp, value in zip(times, series):
            rows.append(dict(datetime=stamp, site_name=station, aqi=value, pm25=value/3,
                             pm10=value/2, o3=value/4, co=0.4, wind_speed=3.0))
    return pd.DataFrame(rows)


def test_future_changes_do_not_change_training_topology_features_or_parameters():
    raw = frames()
    panels = build_panels(raw, causal=True)
    cut, _ = forecast.split_times(panels["aqi"].index)
    # Include a gap across the split to catch look-ahead interpolation.
    raw = raw[~raw.datetime.between(cut-pd.Timedelta(hours=1), cut+pd.Timedelta(hours=1))]
    changed = raw.copy()
    future = changed.datetime > cut
    for column in ("aqi", "pm25", "pm10", "o3"):
        changed.loc[future, column] += np.arange(int(future.sum()))*0.5 + 100
    a, b = build_panels(raw, causal=True), build_panels(changed, causal=True)
    for variable in a:
        pd.testing.assert_frame_equal(a[variable].loc[:cut], b[variable].loc[:cut])
    up_a, up_b = training_upstream(a), training_upstream(b)
    assert up_a == up_b
    result_a = forecast.fit_forecaster(a, upstream=up_a)
    result_b = forecast.fit_forecaster(b, upstream=up_b)
    for left, right in zip(result_a.horizons, result_b.horizons):
        np.testing.assert_allclose(left.model.coefficients, right.model.coefficients)
        np.testing.assert_allclose(left.model.means, right.model.means)
        assert left.model.intercept == pytest.approx(right.model.intercept)


@pytest.mark.parametrize("unit", ["ppb", "µg/m³", "μg/m³"])
def test_ozone_payload_retains_the_numeric_input_unit_and_parity(unit):
    panels = build_panels(frames(), causal=True)
    _, payload = whatif.fit_whatif(panels, ozone_unit=unit)
    ozone = next(row for row in payload["inputs"] if row["key"] == "o3_now")
    assert ozone["unit"] == unit
    for case in payload["parity_cases"]:
        assert whatif.predict_from_payload(payload, case["inputs"]) == pytest.approx(case["expected"], abs=1e-6)


def test_unknown_ozone_unit_is_rejected():
    with pytest.raises(ValueError, match="ozone unit"):
        whatif.fit_whatif(build_panels(frames(), causal=True), ozone_unit="unknown")
