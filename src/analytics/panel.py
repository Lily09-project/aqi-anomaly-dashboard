"""Reshape cleaned long-format observations into aligned station panels."""
from __future__ import annotations

import numpy as np
import pandas as pd

VARIABLES = ("aqi", "pm25", "pm10", "o3", "co", "wind_speed")
GAP_FILL_HOURS = 3


def build_panels(cleaned: pd.DataFrame, *, causal: bool = False) -> dict[str, pd.DataFrame]:
    """Return {variable: DataFrame[time × station]} on a complete hourly grid.

    Short gaps (≤ 3 hours) are interpolated so lag features stay usable;
    longer gaps remain missing and are dropped by each analysis.
    """
    frame = cleaned.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    index = pd.date_range(frame["datetime"].min(), frame["datetime"].max(), freq="h")
    stations = sorted(frame["site_name"].unique())
    panels = {}
    for variable in VARIABLES:
        wide = frame.pivot_table(index="datetime", columns="site_name", values=variable, aggfunc="mean")
        wide = wide.reindex(index=index, columns=stations)
        panels[variable] = wide.ffill(limit=GAP_FILL_HOURS) if causal else fill_short_gaps(wide, GAP_FILL_HOURS)
    return panels


def fill_short_gaps(panel: pd.DataFrame, max_gap: int) -> pd.DataFrame:
    """Interpolate interior gaps of at most ``max_gap`` hours; leave longer gaps empty.

    ``DataFrame.interpolate(limit=...)`` would partially fill long gaps, which
    invents data at their edges, so gap lengths are measured first.
    """
    filled = panel.interpolate(limit_area="inside")
    for column in panel.columns:
        missing = panel[column].isna()
        run_id = (missing != missing.shift()).cumsum()
        run_length = missing.groupby(run_id).transform("sum")
        too_long = missing & (run_length > max_gap)
        filled.loc[too_long, column] = np.nan
    return filled


def hour_of_day_profile(panel: pd.DataFrame) -> pd.DataFrame:
    """Mean value per (hour of day, station)."""
    return panel.groupby(panel.index.hour).mean()


def deseasonalise(panel: pd.DataFrame) -> pd.DataFrame:
    """Remove each station's hour-of-day profile, then standardise."""
    profile = hour_of_day_profile(panel)
    anomalies = panel - profile.reindex(panel.index.hour).to_numpy()
    return (anomalies - anomalies.mean()) / anomalies.std(ddof=0).replace(0, np.nan)
