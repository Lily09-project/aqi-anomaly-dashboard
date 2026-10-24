"""Choose the lowest-risk outdoor window from quantile forecasts.

The P10/P50/P90 forecasts define a piecewise-linear predictive CDF. For a
given AQI threshold (100 for sensitive groups, 150 for everyone) the
probability of exceeding it is read off that CDF for every hour, and the
window with the lowest average exceedance probability wins. The TypeScript
planner in the web app mirrors this module and is tested against it.
"""
from __future__ import annotations

from typing import Mapping, Sequence

THRESHOLDS = {"sensitive": 100.0, "general": 150.0}
_QUANTILE_POINTS = ((0.1, "p10"), (0.5, "p50"), (0.9, "p90"))


def exceedance_probability(hour: Mapping[str, float], threshold: float) -> float:
    """P(AQI > threshold) from a piecewise-linear CDF through P10/P50/P90.

    Beyond P10 and P90 the CDF continues with the slope of the nearest
    segment and is clipped to [0, 1].
    """
    xs = [float(hour[key]) for _, key in _QUANTILE_POINTS]
    ps = [p for p, _ in _QUANTILE_POINTS]
    if threshold <= xs[0]:
        slope = (ps[1] - ps[0]) / max(xs[1] - xs[0], 1e-9)
        cdf = ps[0] - slope * (xs[0] - threshold)
    elif threshold >= xs[2]:
        slope = (ps[2] - ps[1]) / max(xs[2] - xs[1], 1e-9)
        cdf = ps[2] + slope * (threshold - xs[2])
    else:
        segment = 0 if threshold <= xs[1] else 1
        x0, x1 = xs[segment], xs[segment + 1]
        p0, p1 = ps[segment], ps[segment + 1]
        cdf = p0 + (p1 - p0) * (threshold - x0) / max(x1 - x0, 1e-9)
    return 1.0 - min(max(cdf, 0.0), 1.0)


def best_window(forecast: Sequence[Mapping[str, float]], hours: int, sensitivity: str) -> dict[str, float | int] | None:
    """Return the start index, risk and mean P50 of the best window, or None."""
    if hours < 1 or hours > len(forecast):
        return None
    threshold = THRESHOLDS[sensitivity]
    risks = [exceedance_probability(h, threshold) for h in forecast]
    best: dict[str, float | int] | None = None
    for start in range(len(forecast) - hours + 1):
        window = range(start, start + hours)
        risk = sum(risks[i] for i in window) / hours
        mean_p50 = sum(float(forecast[i]["p50"]) for i in window) / hours
        candidate = {"start": start, "risk": risk, "mean_p50": mean_p50}
        # Lower risk wins; ties go to cleaner air, then to the earlier window.
        if best is None or _better(risk, mean_p50, float(best["risk"]), float(best["mean_p50"])):
            best = candidate
    return best


def _better(risk: float, mean_p50: float, best_risk: float, best_mean: float, eps: float = 1e-12) -> bool:
    if risk < best_risk - eps:
        return True
    return abs(risk - best_risk) <= eps and mean_p50 < best_mean - eps
