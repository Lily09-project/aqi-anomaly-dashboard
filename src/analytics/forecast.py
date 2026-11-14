"""24-hour probabilistic AQI forecasts with split-conformal intervals.

One ridge model per horizon (direct multi-step forecasting) predicts AQI
``h`` hours ahead from the current state and the station's climatology.
The published P50 is that point forecast, unshifted. The 80% band is the
point forecast plus or minus one half-width per horizon: the conformal
quantile of the absolute residuals on a held-out calibration window (split
conformal prediction with the absolute-residual score). A final test window
that the model never saw measures whether the band really covers 80%.

The calibration window's median residual is reported as a diagnostic but is
not added to the forecast. It is estimated from about nine serially
dependent days and did not carry over to the following days in rolling
backtests, so applying it made the point forecast worse; a bias in the
calibration window widens the band instead of moving its centre.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.analytics.ridge import RidgeModel, fit_ridge

HORIZONS = tuple(range(1, 25))
TRAIN_SHARE = 0.70
CALIBRATION_SHARE = 0.15
INTERVAL_LEVEL = 0.8  # central band published as P10–P90
FEATURE_NAMES = (
    "aqi_now",
    "aqi_lag1",
    "aqi_lag3",
    "aqi_mean6",
    "pm25_now",
    "wind_now",
    "clim_now",
    "clim_target",
)
# Added when upstream stations are known: how far above its usual level the
# nearest upstream station is right now (0 for stations without one).
UPSTREAM_FEATURE = "upstream_anomaly"


@dataclass
class HorizonResult:
    horizon: int
    model: RidgeModel
    half_width: float  # P90 − P50 = P50 − P10
    calibration_median_residual: float  # diagnostic only, never applied
    calibration_size: int
    test_coverage: float
    test_mae: float
    shifted_test_mae: float  # diagnostic: test MAE had the calibration median been added
    persistence_mae: float
    climatology_mae: float
    test_size: int
    station_mae: dict[str, float] = field(default_factory=dict)


@dataclass
class ForecastResult:
    horizons: list[HorizonResult]
    split: dict[str, str]
    features: list[str]
    forecasts: dict[str, list[dict[str, float | str | int]]] = field(default_factory=dict)


def conformal_half_width(residuals: np.ndarray, level: float = INTERVAL_LEVEL) -> float:
    """Split-conformal quantile of |residual|: the ceil((n + 1) · level)-th smallest score."""
    scores = np.sort(np.abs(np.asarray(residuals, dtype=float)))
    if len(scores) == 0 or not np.isfinite(scores).all():
        raise ValueError("calibration residuals must be a non-empty finite array")
    if not 0 < level < 1:
        raise ValueError("level must be between 0 and 1")
    rank = min(math.ceil((len(scores) + 1) * level), len(scores))
    return float(scores[rank - 1])


def _climatology(aqi: pd.DataFrame, until: pd.Timestamp) -> pd.DataFrame:
    """Station × hour-of-day mean AQI using only data up to ``until``."""
    history = aqi.loc[:until]
    return history.groupby(history.index.hour).mean()


def design_matrix(
    panels: dict[str, pd.DataFrame],
    climatology: pd.DataFrame,
    horizon: int,
    upstream: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Long table of features at each origin and the target ``horizon`` hours later."""
    aqi = panels["aqi"]
    anomaly = aqi - climatology.reindex(aqi.index.hour).to_numpy()
    rows = []
    for station in aqi.columns:
        series = aqi[station]
        frame = pd.DataFrame(
            {
                "origin": aqi.index,
                "station": station,
                "aqi_now": series.to_numpy(),
                "aqi_lag1": series.shift(1).to_numpy(),
                "aqi_lag3": series.shift(3).to_numpy(),
                "aqi_mean6": series.rolling(6, min_periods=4).mean().to_numpy(),
                "pm25_now": panels["pm25"][station].to_numpy(),
                "wind_now": panels["wind_speed"][station].to_numpy(),
                "clim_now": climatology[station].reindex(aqi.index.hour).to_numpy(),
                "clim_target": climatology[station].reindex((aqi.index + pd.Timedelta(hours=horizon)).hour).to_numpy(),
                "target": series.shift(-horizon).to_numpy(),
            }
        )
        if upstream is not None:
            source = upstream.get(station)
            frame[UPSTREAM_FEATURE] = anomaly[source].to_numpy() if source else 0.0
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def split_times(index: pd.DatetimeIndex) -> tuple[pd.Timestamp, pd.Timestamp]:
    n = len(index)
    train_end = index[int(n * TRAIN_SHARE) - 1]
    calibration_end = index[int(n * (TRAIN_SHARE + CALIBRATION_SHARE)) - 1]
    return train_end, calibration_end


def fit_forecaster(
    panels: dict[str, pd.DataFrame],
    alpha: float = 1.0,
    upstream: dict[str, str] | None = None,
) -> ForecastResult:
    aqi = panels["aqi"]
    train_end, calibration_end = split_times(aqi.index)
    climatology = _climatology(aqi, train_end)
    results = []
    features = list(FEATURE_NAMES) + ([UPSTREAM_FEATURE] if upstream is not None else [])
    for horizon in HORIZONS:
        table = design_matrix(panels, climatology, horizon, upstream).dropna()
        # The target must also fall inside the split, so no future value leaks backwards.
        target_time = table["origin"] + pd.Timedelta(hours=horizon)
        train = table[target_time <= train_end]
        calibration = table[(table["origin"] > train_end) & (target_time <= calibration_end)]
        test = table[table["origin"] > calibration_end]
        model = fit_ridge(train[features].to_numpy(), train["target"].to_numpy(), alpha=alpha)
        residuals = calibration["target"].to_numpy() - model.predict(calibration[features].to_numpy())
        half_width = conformal_half_width(residuals)
        median_residual = float(np.median(residuals))
        point = model.predict(test[features].to_numpy())
        actual = test["target"].to_numpy()
        inside = np.abs(actual - point) <= half_width
        errors = pd.Series(np.abs(actual - point), index=test["station"].to_numpy())
        results.append(
            HorizonResult(
                horizon=horizon,
                model=model,
                half_width=half_width,
                calibration_median_residual=median_residual,
                calibration_size=int(len(calibration)),
                test_coverage=float(inside.mean()),
                test_mae=float(errors.mean()),
                shifted_test_mae=float(np.abs(actual - (point + median_residual)).mean()),
                persistence_mae=float(np.abs(actual - test["aqi_now"].to_numpy()).mean()),
                climatology_mae=float(np.abs(actual - test["clim_target"].to_numpy()).mean()),
                test_size=int(len(test)),
                station_mae={k: float(v) for k, v in errors.groupby(level=0).mean().items()},
            )
        )
    result = ForecastResult(
        horizons=results,
        features=features,
        split={
            "train_end": train_end.isoformat(),
            "calibration_end": calibration_end.isoformat(),
            "test_end": aqi.index[-1].isoformat(),
        },
    )
    result.forecasts = forecast_latest(panels, climatology, result, upstream)
    return result


def forecast_latest(
    panels: dict[str, pd.DataFrame],
    climatology: pd.DataFrame,
    result: ForecastResult,
    upstream: dict[str, str] | None = None,
) -> dict[str, list[dict[str, float | str | int]]]:
    """P10/P50/P90 for the next 24 hours from the last observed hour."""
    aqi = panels["aqi"]
    origin = aqi.index[-1]
    out: dict[str, list[dict[str, float | str | int]]] = {}
    for horizon_result in result.horizons:
        table = design_matrix(panels, climatology, horizon_result.horizon, upstream)
        latest = table[table["origin"] == origin].set_index("station")
        for station in aqi.columns:
            row = latest.loc[station, result.features]
            if row.isna().any():
                continue
            point = float(horizon_result.model.predict(row.to_numpy(dtype=float)[None, :])[0])
            half_width = horizon_result.half_width
            out.setdefault(station, []).append(
                {
                    "h": horizon_result.horizon,
                    "t": (origin + pd.Timedelta(hours=horizon_result.horizon)).isoformat(),
                    "p10": round(max(point - half_width, 0.0), 1),
                    "p50": round(max(point, 0.0), 1),
                    "p90": round(max(point + half_width, 0.0), 1),
                }
            )
    return out
