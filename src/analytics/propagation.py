"""Lead–lag analysis: which stations see pollution first.

PM2.5 is deseasonalised per station (hour-of-day profile removed, then
standardised) so shared daily rhythms such as rush hour do not create false
links. For every ordered pair the cross-correlation is scanned over ±12
hours; a peak at a positive lag means the first station leads the second.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.analytics.panel import deseasonalise

MAX_LAG = 12
MIN_CORRELATION = 0.3


@dataclass(frozen=True)
class Link:
    upstream: str
    downstream: str
    lag_hours: int
    correlation: float
    synchronous_correlation: float


def cross_correlation(a: np.ndarray, b: np.ndarray, max_lag: int = MAX_LAG) -> dict[int, float]:
    """corr(a[t], b[t + k]) for k in [-max_lag, max_lag], ignoring missing pairs."""
    out: dict[int, float] = {}
    n = len(a)
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            x, y = a[: n - k], b[k:]
        else:
            x, y = a[-k:], b[: n + k]
        mask = ~(np.isnan(x) | np.isnan(y))
        if mask.sum() < 30:
            out[k] = float("nan")
            continue
        out[k] = float(np.corrcoef(x[mask], y[mask])[0, 1])
    return out


def lead_lag_links(pm25: pd.DataFrame, max_lag: int = MAX_LAG, min_correlation: float = MIN_CORRELATION) -> tuple[list[Link], dict[str, dict[str, dict[str, float]]]]:
    """Return significant directed links and the full peak-correlation matrix."""
    anomalies = deseasonalise(pm25)
    stations = list(anomalies.columns)
    links: list[Link] = []
    matrix: dict[str, dict[str, dict[str, float]]] = {s: {} for s in stations}
    for i, a in enumerate(stations):
        for b in stations[i + 1 :]:
            ccf = cross_correlation(anomalies[a].to_numpy(), anomalies[b].to_numpy(), max_lag)
            valid = {k: v for k, v in ccf.items() if not np.isnan(v)}
            if not valid:
                continue
            lag = max(valid, key=lambda k: (valid[k], -abs(k)))
            peak = valid[lag]
            matrix[a][b] = {"lag": lag, "r": round(peak, 3)}
            matrix[b][a] = {"lag": -lag, "r": round(peak, 3)}
            if peak < min_correlation or lag == 0:
                continue
            upstream, downstream = (a, b) if lag > 0 else (b, a)
            links.append(Link(upstream, downstream, abs(lag), round(peak, 3), round(valid.get(0, float("nan")), 3)))
    links.sort(key=lambda link: (link.upstream, link.lag_hours, link.downstream))
    return links, matrix


def nearest_upstream(links: list[Link]) -> dict[str, Link]:
    """For each station, the link with the shortest lead time (ties: higher r)."""
    best: dict[str, Link] = {}
    for link in links:
        current = best.get(link.downstream)
        if current is None or (link.lag_hours, -link.correlation) < (current.lag_hours, -current.correlation):
            best[link.downstream] = link
    return best


def strongest_episode(pm25: pd.DataFrame, stations: list[str], before: int = 18, after: int = 30) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Window around the hour when the listed stations were jointly most polluted."""
    anomalies = deseasonalise(pm25[stations])
    joint = anomalies.mean(axis=1).rolling(6, min_periods=3).mean()
    peak = joint.idxmax()
    start = max(pm25.index[0], peak - pd.Timedelta(hours=before))
    end = min(pm25.index[-1], peak + pd.Timedelta(hours=after))
    return start, end
