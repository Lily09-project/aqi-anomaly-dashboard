"""Distribution drift between a recent window and the window before it."""
from __future__ import annotations

import numpy as np
import pandas as pd

CURRENT_DAYS = 7
REFERENCE_DAYS = 14
WATCH = 0.5
ALERT = 1.0


def mean_shift(panel: pd.DataFrame, current_days: int = CURRENT_DAYS, reference_days: int = REFERENCE_DAYS) -> list[dict[str, float | str]]:
    """Per-station shift of the recent mean, in reference standard deviations."""
    end = panel.index[-1]
    current = panel.loc[end - pd.Timedelta(days=current_days) + pd.Timedelta(hours=1) : end]
    reference_end = current.index[0] - pd.Timedelta(hours=1)
    reference = panel.loc[reference_end - pd.Timedelta(days=reference_days) + pd.Timedelta(hours=1) : reference_end]
    rows = []
    for station in panel.columns:
        sd = float(reference[station].std())
        shift = (float(current[station].mean()) - float(reference[station].mean())) / sd if sd > 0 else float("nan")
        status = "insufficient" if np.isnan(shift) else "alert" if abs(shift) >= ALERT else "watch" if abs(shift) >= WATCH else "stable"
        rows.append(
            {
                "station": station,
                "reference_mean": round(float(reference[station].mean()), 1),
                "current_mean": round(float(current[station].mean()), 1),
                "shift_sd": round(shift, 2) if not np.isnan(shift) else None,
                "status": status,
            }
        )
    return rows
