from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src.analytics import aqi_scale, drift, planner
from src.analytics.panel import build_panels, deseasonalise, hour_of_day_profile
from src.analytics.ridge import fit_ridge


def test_sub_index_interpolates_inside_bands_and_handles_edges() -> None:
    assert aqi_scale.sub_index(0, aqi_scale.PM25) == 0
    assert aqi_scale.sub_index(15.4, aqi_scale.PM25) == pytest.approx(50)
    assert aqi_scale.sub_index(35.4, aqi_scale.PM25) == pytest.approx(100)
    assert aqi_scale.sub_index(25.45, aqi_scale.PM25) == pytest.approx(75.5, abs=0.1)
    assert aqi_scale.sub_index(15.45, aqi_scale.PM25) == pytest.approx(51)  # gap between bands → upper band
    assert aqi_scale.sub_index(999, aqi_scale.PM25) == 500
    assert aqi_scale.sub_index(-5, aqi_scale.PM10) == 0
    assert math.isnan(aqi_scale.sub_index(float("nan"), aqi_scale.O3_PPB))


def test_aqi_is_the_worst_sub_index_and_categories_follow_breakpoints() -> None:
    assert aqi_scale.aqi(10, 200, 30) == pytest.approx(aqi_scale.sub_index(200, aqi_scale.PM10))
    assert aqi_scale.aqi(float("nan"), 40, float("nan")) == pytest.approx(aqi_scale.sub_index(40, aqi_scale.PM10))
    assert math.isnan(aqi_scale.aqi(float("nan"), float("nan"), float("nan")))
    assert aqi_scale.category(50) == ("good", "良好")
    assert aqi_scale.category(51) == ("moderate", "普通")
    assert aqi_scale.category(150)[0] == "sensitive"
    assert aqi_scale.category(320)[0] == "hazardous"
    assert aqi_scale.category(900)[0] == "hazardous"
    assert aqi_scale.category(float("nan")) == ("unknown", "無資料")


def _long_frame(hours: int = 96) -> pd.DataFrame:
    times = pd.date_range("2026-01-01", periods=hours, freq="h")
    rows = []
    for station, offset in (("A", 0.0), ("B", 10.0)):
        for i, t in enumerate(times):
            value = 50 + offset + 10 * math.sin(2 * math.pi * t.hour / 24) + (i % 5)
            rows.append({"datetime": t, "site_name": station, "aqi": value, "pm25": value / 3, "pm10": value / 2, "o3": 30.0, "co": 0.4, "wind_speed": 3.0})
    return pd.DataFrame(rows)


def test_panels_align_stations_and_fill_only_short_gaps() -> None:
    frame = _long_frame()
    frame = frame[~((frame.site_name == "A") & frame.datetime.between("2026-01-02 00:00", "2026-01-02 01:00"))]
    frame = frame[~((frame.site_name == "B") & frame.datetime.between("2026-01-03 00:00", "2026-01-03 05:00"))]
    panels = build_panels(frame)
    assert list(panels["aqi"].columns) == ["A", "B"]
    assert len(panels["aqi"]) == 96
    assert panels["aqi"]["A"].isna().sum() == 0  # 2-hour gap interpolated
    assert panels["aqi"]["B"].isna().sum() == 6  # 6-hour gap kept missing
    assert hour_of_day_profile(panels["aqi"]).shape == (24, 2)
    anomalies = deseasonalise(panels["aqi"])
    assert abs(float(anomalies["A"].mean())) < 1e-9
    assert float(anomalies["A"].std(ddof=0)) == pytest.approx(1.0)


def test_ridge_recovers_a_linear_relationship_and_explains_contributions() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(500, 3))
    y = 4 + 2 * x[:, 0] - 3 * x[:, 1] + rng.normal(0, 0.01, 500)
    model = fit_ridge(x, y, alpha=1e-6)
    assert model.predict(np.array([[1.0, 1.0, 0.0]]))[0] == pytest.approx(4 + 2 - 3, abs=0.05)
    contributions = model.contributions(x[:1])
    assert contributions.sum() + model.intercept == pytest.approx(model.predict(x[:1])[0])
    constant = fit_ridge(np.ones((10, 1)), np.arange(10.0))
    assert constant.scales[0] == 1.0
    with pytest.raises(ValueError):
        fit_ridge(np.ones(5), np.ones(5))


FORECAST = [
    {"p10": 40, "p50": 60, "p90": 90},
    {"p10": 70, "p50": 110, "p90": 160},
    {"p10": 30, "p50": 45, "p90": 70},
    {"p10": 20, "p50": 35, "p90": 55},
    {"p10": 90, "p50": 130, "p90": 200},
]


def test_exceedance_probability_reads_the_piecewise_cdf() -> None:
    hour = {"p10": 40, "p50": 60, "p90": 100}
    assert planner.exceedance_probability(hour, 60) == pytest.approx(0.5)
    assert planner.exceedance_probability(hour, 40) == pytest.approx(0.9)
    assert planner.exceedance_probability(hour, 80) == pytest.approx(0.3)
    assert planner.exceedance_probability(hour, 140) == pytest.approx(0.0)
    assert planner.exceedance_probability(hour, 0) == pytest.approx(1.0)
    # Below P10 the CDF keeps the first segment's slope (0.4 / 20 per AQI point).
    assert planner.exceedance_probability(hour, 38) == pytest.approx(1 - (0.1 - 0.02 * 2))
    assert planner.exceedance_probability(hour, 30) == pytest.approx(1.0)  # extrapolated CDF clipped at 0


def test_best_window_is_the_lowest_risk_candidate() -> None:
    for hours in (1, 2, 3):
        best = planner.best_window(FORECAST, hours, "sensitive")
        assert best is not None
        risks = []
        for start in range(len(FORECAST) - hours + 1):
            window = FORECAST[start : start + hours]
            risks.append(sum(planner.exceedance_probability(h, 100) for h in window) / hours)
        assert best["risk"] == pytest.approx(min(risks))
    assert planner.best_window(FORECAST, 1, "sensitive")["start"] == 3
    assert planner.best_window(FORECAST, 6, "general") is None
    assert planner.best_window(FORECAST, 0, "general") is None


def test_best_window_breaks_ties_by_cleaner_air_then_earlier_start() -> None:
    clean = [{"p10": 10, "p50": 20, "p90": 30}, {"p10": 5, "p50": 15, "p90": 25}, {"p10": 5, "p50": 15, "p90": 25}]
    best = planner.best_window(clean, 1, "general")
    assert best["start"] == 1  # all zero risk; first of the two cleanest hours


def test_drift_classifies_mean_shifts() -> None:
    index = pd.date_range("2026-01-01", periods=21 * 24, freq="h")
    rng = np.random.default_rng(1)
    reference = rng.normal(20, 2, 14 * 24)
    panel = pd.DataFrame(
        {
            "stable": np.concatenate([reference, rng.normal(20, 2, 7 * 24)]),
            "alert": np.concatenate([reference, rng.normal(26, 2, 7 * 24)]),
            "flat": np.ones(21 * 24),
        },
        index=index,
    )
    rows = {r["station"]: r for r in drift.mean_shift(panel)}
    assert rows["stable"]["status"] == "stable"
    assert rows["alert"]["status"] == "alert"
    assert rows["alert"]["shift_sd"] > 2
    assert rows["flat"]["status"] == "insufficient"
