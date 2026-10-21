from __future__ import annotations

import pandas as pd


def hourly_segments(frame: pd.DataFrame) -> pd.Series:
    """Label contiguous station-hour runs in already station/time-sorted rows.

    Missing identities/timestamps and duplicate hours are boundaries, never
    permission to borrow values across an unknown station or elapsed gap.
    Convert nullable/Arrow booleans before accumulation: Arrow bool cumsum
    is not supported by all supported pandas/PyArrow combinations.
    """
    sites = frame["site_name"]
    times = frame["datetime"]
    previous_sites = sites.shift(1)
    previous_times = times.shift(1)
    starts = (
        sites.isna()
        | previous_sites.isna()
        | sites.ne(previous_sites)
        | times.isna()
        | previous_times.isna()
        | times.sub(previous_times).ne(pd.Timedelta(hours=1))
    )
    return starts.fillna(True).astype("int64").cumsum()
