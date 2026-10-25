"""AQI sub-indices from pollutant concentrations.

Breakpoints follow the Ministry of Environment AQI tables. The official
index uses rolling averages (24-hour PM2.5/PM10, 8-hour O3); this demo
applies the same breakpoints to hourly values, which is documented as a
simplification wherever the index is shown.
"""
from __future__ import annotations

import math
from typing import Sequence

# (concentration low, concentration high, index low, index high)
Breakpoints = Sequence[tuple[float, float, int, int]]

PM25: Breakpoints = (
    (0.0, 15.4, 0, 50),
    (15.5, 35.4, 51, 100),
    (35.5, 54.4, 101, 150),
    (54.5, 150.4, 151, 200),
    (150.5, 250.4, 201, 300),
    (250.5, 350.4, 301, 400),
    (350.5, 500.4, 401, 500),
)
PM10: Breakpoints = (
    (0, 54, 0, 50),
    (55, 125, 51, 100),
    (126, 254, 101, 150),
    (255, 354, 151, 200),
    (355, 424, 201, 300),
    (425, 504, 301, 400),
    (505, 604, 401, 500),
)
O3_PPB: Breakpoints = (
    (0, 54, 0, 50),
    (55, 70, 51, 100),
    (71, 85, 101, 150),
    (86, 105, 151, 200),
    (106, 200, 201, 300),
)

CATEGORIES: tuple[tuple[int, str, str], ...] = (
    (50, "good", "良好"),
    (100, "moderate", "普通"),
    (150, "sensitive", "對敏感族群不健康"),
    (200, "unhealthy", "對所有族群不健康"),
    (300, "very-unhealthy", "非常不健康"),
    (500, "hazardous", "危害"),
)


def sub_index(concentration: float, table: Breakpoints) -> float:
    """Linear interpolation inside the matching breakpoint band."""
    if concentration is None or math.isnan(concentration):
        return float("nan")
    value = max(float(concentration), 0.0)
    for c_low, c_high, i_low, i_high in table:
        # Bands are reported at one decimal, so values between bands belong to the upper one.
        if value <= c_high:
            value = max(value, c_low)
            return i_low + (i_high - i_low) * (value - c_low) / (c_high - c_low)
    return float(table[-1][3])


def aqi(pm25: float, pm10: float, o3_ppb: float) -> float:
    """The index is the worst sub-index; missing pollutants are ignored."""
    candidates = [sub_index(pm25, PM25), sub_index(pm10, PM10), sub_index(o3_ppb, O3_PPB)]
    valid = [c for c in candidates if not math.isnan(c)]
    return max(valid) if valid else float("nan")


def category(index: float) -> tuple[str, str]:
    """Return (key, Chinese label) for an AQI value."""
    if index is None or math.isnan(index):
        return "unknown", "無資料"
    for upper, key, label in CATEGORIES:
        if index <= upper:
            return key, label
    return CATEGORIES[-1][1], CATEGORIES[-1][2]
