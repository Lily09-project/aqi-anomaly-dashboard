"""An interpretable next-hour model the browser can evaluate.

A ridge regression on a handful of physical inputs predicts next-hour AQI.
Its means, scales and coefficients are exported so the web app can run the
same model as the user drags sliders, and a fixed set of parity cases is
exported with Python's predictions so both implementations stay identical.
"""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from src.analytics.forecast import split_times
from src.analytics.ridge import RidgeModel, fit_ridge

PARAM_DIGITS = 9

INPUTS: tuple[tuple[str, str, str], ...] = (
    ("aqi_now", "目前 AQI", ""),
    ("pm25_now", "目前 PM2.5", "µg/m³"),
    ("pm10_now", "目前 PM10", "µg/m³"),
    ("o3_now", "目前臭氧", "ppb"),
    ("wind_now", "風速", "m/s"),
    ("hour", "時刻", "時"),
)


def _features(table: pd.DataFrame) -> np.ndarray:
    """Hour enters as a sine/cosine pair so 23:00 and 00:00 are neighbours."""
    angle = 2 * np.pi * table["hour"].to_numpy(dtype=float) / 24
    base = table[[name for name, _, _ in INPUTS if name != "hour"]].to_numpy(dtype=float)
    return np.column_stack([base, np.sin(angle), np.cos(angle)])


def training_table(panels: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for station in panels["aqi"].columns:
        frames.append(
            pd.DataFrame(
                {
                    "origin": panels["aqi"].index,
                    "aqi_now": panels["aqi"][station].to_numpy(),
                    "pm25_now": panels["pm25"][station].to_numpy(),
                    "pm10_now": panels["pm10"][station].to_numpy(),
                    "o3_now": panels["o3"][station].to_numpy(),
                    "wind_now": panels["wind_speed"][station].to_numpy(),
                    "hour": panels["aqi"].index.hour,
                    "target": panels["aqi"][station].shift(-1).to_numpy(),
                }
            )
        )
    return pd.concat(frames, ignore_index=True).dropna()


def fit_whatif(panels: dict[str, pd.DataFrame], alpha: float = 1.0) -> tuple[RidgeModel, dict[str, Any]]:
    table = training_table(panels)
    train_end, calibration_end = split_times(panels["aqi"].index)
    train = table[table["origin"] < train_end]
    calibration = table[(table["origin"] >= train_end) & (table["origin"] < calibration_end)]
    model = fit_ridge(_features(train), train["target"].to_numpy(), alpha=alpha)
    residuals = calibration["target"].to_numpy() - model.predict(_features(calibration))
    ranges = {
        name: {"min": round(float(table[name].quantile(0.01)), 1), "max": round(float(table[name].quantile(0.99)), 1), "default": round(float(table[name].median()), 1)}
        for name, _, _ in INPUTS
        if name != "hour"
    }
    ranges["hour"] = {"min": 0, "max": 23, "default": 8}
    # Parameters are rounded so the export is identical across platforms (BLAS
    # results differ in the last bits); the parity cases are then computed from
    # the rounded payload with the same arithmetic the browser uses.
    payload: dict[str, Any] = {
        "inputs": [{"key": k, "label": label, "unit": unit, **ranges[k]} for k, label, unit in INPUTS],
        "feature_order": [name for name, _, _ in INPUTS if name != "hour"] + ["hour_sin", "hour_cos"],
        "means": [round(float(v), PARAM_DIGITS) for v in model.means],
        "scales": [round(float(v), PARAM_DIGITS) for v in model.scales],
        "coefficients": [round(float(v), PARAM_DIGITS) for v in model.coefficients],
        "intercept": round(float(model.intercept), PARAM_DIGITS),
        "residual_p10": round(float(np.quantile(residuals, 0.1)), PARAM_DIGITS),
        "residual_p90": round(float(np.quantile(residuals, 0.9)), PARAM_DIGITS),
        "calibration_size": int(len(calibration)),
    }
    cases = []
    rng = np.random.default_rng(7)
    for _ in range(12):
        case = {name: round(float(rng.uniform(r["min"], r["max"])), 1) for name, r in ranges.items()}
        case["hour"] = int(round(case["hour"]))
        cases.append({"inputs": case, "expected": round(predict_from_payload(payload, case), PARAM_DIGITS)})
    payload["parity_cases"] = cases
    return model, payload


def predict_from_payload(payload: dict[str, Any], inputs: dict[str, float]) -> float:
    """Reference implementation of what the browser computes."""
    angle = 2 * math.pi * float(inputs["hour"]) / 24
    values = [float(inputs[name]) for name in payload["feature_order"][:-2]] + [math.sin(angle), math.cos(angle)]
    standardised = [(v - m) / s for v, m, s in zip(values, payload["means"], payload["scales"])]
    return payload["intercept"] + sum(z * c for z, c in zip(standardised, payload["coefficients"]))
