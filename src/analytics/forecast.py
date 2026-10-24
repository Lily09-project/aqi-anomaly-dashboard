"""24-hour probabilistic AQI forecasts with split-conformal intervals.

One ridge model per horizon (direct multi-step forecasting) predicts AQI
``h`` hours ahead from the current state and the station's climatology.
Residual quantiles on a held-out calibration window turn the point forecast
into P10/P50/P90 bands (split conformal prediction); a final test window
that the model never saw measures whether the 80% band really covers 80%.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.analytics.ridge import RidgeModel, fit_ridge

HORIZONS = tuple(range(1, 25))
TRAIN_SHARE = 0.70
CALIBRATION_SHARE = 0.15
QUANTILES = (0.1, 0.5, 0.9)
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
    residual_quantiles: tuple[float, float, float]
    test_coverage: float
    test_mae: float
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
        q10, q50, q90 = (float(np.quantile(residuals, q)) for q in QUANTILES)
        point = model.predict(test[features].to_numpy())
        actual = test["target"].to_numpy()
        inside = (actual >= point + q10) & (actual <= point + q90)
        errors = pd.Series(np.abs(actual - (point + q50)), index=test["station"].to_numpy())
        results.append(
            HorizonResult(
                horizon=horizon,
                model=model,
                residual_quantiles=(q10, q50, q90),
                test_coverage=float(inside.mean()),
                test_mae=float(np.abs(actual - (point + q50)).mean()),
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
            q10, q50, q90 = horizon_result.residual_quantiles
            out.setdefault(station, []).append(
                {
                    "h": horizon_result.horizon,
                    "t": (origin + pd.Timedelta(hours=horizon_result.horizon)).isoformat(),
                    "p10": round(max(point + q10, 0.0), 1),
                    "p50": round(max(point + q50, 0.0), 1),
                    "p90": round(max(point + q90, 0.0), 1),
                }
            )
    return out
