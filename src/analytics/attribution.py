"""Explainable anomaly events.

Each station gets a robust baseline per hour of day (median and MAD), so a
reading is unusual only relative to what that station normally sees at
that hour. Hours with a robust PM2.5 z-score above the threshold are merged
into events; each event is explained by ranking every variable's z-score,
labelled regional or local, and matched to its most similar past events.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

EXPLAINED_VARIABLES = ("pm25", "pm10", "co", "o3", "wind_speed")
VARIABLE_LABELS = {"pm25": "PM2.5", "pm10": "PM10", "co": "一氧化碳", "o3": "臭氧", "wind_speed": "風速"}
Z_THRESHOLD = 4.5
MERGE_GAP_HOURS = 1
# Matches the longest transport delay down the west coast (see propagation).
REGIONAL_WINDOW_HOURS = 10
REGIONAL_MIN_OTHER_STATIONS = 2
MAD_TO_SD = 1.4826


@dataclass
class Event:
    event_id: str
    station: str
    start: pd.Timestamp
    end: pd.Timestamp
    peak: pd.Timestamp
    peak_aqi: float
    peak_pm25: float
    z: dict[str, float]
    kind: str = "local"
    similar: list[dict[str, float | str]] = field(default_factory=list)

    @property
    def duration_hours(self) -> int:
        return int((self.end - self.start) / pd.Timedelta(hours=1)) + 1

    def drivers(self) -> list[dict[str, float | str]]:
        ranked = sorted(self.z.items(), key=lambda kv: -abs(kv[1]))
        return [{"variable": k, "label": VARIABLE_LABELS[k], "z": round(v, 2)} for k, v in ranked]


def robust_z(panel: pd.DataFrame) -> pd.DataFrame:
    """(x − median) / (1.4826 · MAD), computed per station and hour of day."""
    hours = panel.index.hour
    median = panel.groupby(hours).median()
    mad = (panel - median.reindex(hours).to_numpy()).abs().groupby(hours).median() * MAD_TO_SD
    mad = mad.where(mad > 1e-9)
    return (panel - median.reindex(hours).to_numpy()) / mad.reindex(hours).to_numpy()


def _runs(flags: pd.Series, gap: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    times = list(flags.index[flags.to_numpy()])
    runs: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for t in times:
        if runs and (t - runs[-1][1]) <= pd.Timedelta(hours=gap + 1):
            runs[-1] = (runs[-1][0], t)
        else:
            runs.append((t, t))
    return runs


def detect_events(
    panels: dict[str, pd.DataFrame],
    threshold: float = Z_THRESHOLD,
    regional_window_hours: int = REGIONAL_WINDOW_HOURS,
) -> list[Event]:
    zscores = {v: robust_z(panels[v]) for v in EXPLAINED_VARIABLES}
    flags = zscores["pm25"] >= threshold
    events: list[Event] = []
    for station in panels["pm25"].columns:
        for start, end in _runs(flags[station].fillna(False), MERGE_GAP_HOURS):
            window = zscores["pm25"].loc[start:end, station]
            peak = window.idxmax()
            z = {v: float(zscores[v].at[peak, station]) for v in EXPLAINED_VARIABLES if not np.isnan(zscores[v].at[peak, station])}
            events.append(
                Event(
                    event_id=f"{station}-{peak.strftime('%Y%m%d%H')}",
                    station=station,
                    start=start,
                    end=end,
                    peak=peak,
                    peak_aqi=float(panels["aqi"].at[peak, station]),
                    peak_pm25=float(panels["pm25"].at[peak, station]),
                    z=z,
                )
            )
    _label_regional(events, regional_window_hours)
    _attach_similar(events)
    events.sort(key=lambda e: (e.peak, e.station))
    return events


def _label_regional(events: list[Event], window_hours: int) -> None:
    window = pd.Timedelta(hours=window_hours)
    for event in events:
        others = {o.station for o in events if o.station != event.station and abs(o.peak - event.peak) <= window}
        event.kind = "regional" if len(others) >= REGIONAL_MIN_OTHER_STATIONS else "local"


def _attach_similar(events: list[Event], top_n: int = 3) -> None:
    if len(events) < 2:
        return
    vectors = np.array([[e.z.get(v, 0.0) for v in EXPLAINED_VARIABLES] for e in events])
    for i, event in enumerate(events):
        distances = np.sqrt(((vectors - vectors[i]) ** 2).sum(axis=1))
        distances[i] = np.inf
        order = np.argsort(distances, kind="stable")[:top_n]
        event.similar = [{"event_id": events[j].event_id, "distance": round(float(distances[j]), 2)} for j in order if np.isfinite(distances[j])]


def recall(detected: list[Event], truth: pd.DataFrame, tolerance_hours: int = 1) -> float:
    """Share of ground-truth events overlapped by a detected event at the same station."""
    if truth.empty:
        return float("nan")
    slack = pd.Timedelta(hours=tolerance_hours)
    hits = 0
    for row in truth.itertuples(index=False):
        start, end = pd.Timestamp(row.start) - slack, pd.Timestamp(row.end) + slack
        if any(e.station == row.site_name and e.start <= end and e.end >= start for e in detected):
            hits += 1
    return hits / len(truth)
