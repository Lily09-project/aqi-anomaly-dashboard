"""Reproducible synthetic air-quality data with known, testable structure.

The generator is a small physical caricature rather than random noise:

* A regional pollution plume drifts down Taiwan's west coast (north-east
  monsoon pattern). Each western station sees the same plume after a fixed
  delay (``TRANSPORT_LAG_HOURS``), so the propagation analysis has a ground
  truth to recover. The east-coast stations are shielded and never see it.
* Local emission events (traffic, burning) are injected at random stations
  and written to ``injected_events.csv`` so anomaly recall can be measured.
* Wind ventilates pollution, ozone follows the afternoon sun, and the AQI is
  computed from the concentrations with the official breakpoint tables.

Everything is driven by a seed and a fixed end date from ``config.yaml``, so
two runs produce byte-identical files.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.analytics import aqi_scale
from src.source_metadata import build_source_metadata, file_sha256, frame_summary, write_source_metadata
from src.utils import load_config, project_path, resolve_path, write_csv

# site, county, background PM2.5 (µg/m3), plume gain
SITES: tuple[tuple[str, str, float, float], ...] = (
    ("松山測站", "臺北市", 14.0, 1.0),
    ("板橋測站", "新北市", 16.0, 1.0),
    ("桃園測站", "桃園市", 17.0, 0.95),
    ("西屯測站", "臺中市", 19.0, 0.9),
    ("安南測站", "臺南市", 21.0, 0.85),
    ("前金測站", "高雄市", 24.0, 0.85),
    ("宜蘭測站", "宜蘭縣", 11.0, 0.0),
    ("花蓮測站", "花蓮縣", 9.0, 0.0),
)

# Hours after the plume reaches Taipei (松山) that each western station sees it.
TRANSPORT_LAG_HOURS: dict[str, int] = {
    "松山測站": 0,
    "板橋測站": 1,
    "桃園測站": 2,
    "西屯測站": 5,
    "安南測站": 8,
    "前金測站": 10,
}

MIN_SAMPLE_DAYS = 1
MAX_SAMPLE_DAYS = 366
DEFAULT_DAYS = 60
DEFAULT_END_DATE = "2026-10-20"
LOCAL_EVENTS = 14
PLUME_EPISODES = 7
MISSING_RATE = 0.004


def _end_date(config: dict) -> date:
    configured = config.get("sample", {}).get("end_date", DEFAULT_END_DATE)
    return pd.Timestamp(configured).date()


def _ar1(rng: np.random.Generator, n: int, phi: float, sd: float) -> np.ndarray:
    noise = rng.normal(0, sd, n)
    out = np.empty(n)
    out[0] = noise[0] / np.sqrt(1 - phi**2)
    for i in range(1, n):
        out[i] = phi * out[i - 1] + noise[i]
    return out


def _plume(rng: np.random.Generator, n: int, pad: int) -> tuple[np.ndarray, list[dict[str, float]]]:
    """Regional plume intensity on an extended time axis (index 0 = -pad hours)."""
    total = n + pad
    t = np.arange(total, dtype=float)
    plume = np.zeros(total)
    episodes = []
    centres = np.sort(rng.choice(np.arange(pad + 48, total - 24), size=PLUME_EPISODES, replace=False))
    for centre in centres:
        amplitude = rng.uniform(22, 40)
        width = rng.uniform(5, 10)
        plume += amplitude * np.exp(-0.5 * ((t - centre) / width) ** 2)
        episodes.append({"centre_index": float(centre - pad), "amplitude": float(amplitude), "width": float(width)})
    plume += np.maximum(_ar1(rng, total, 0.97, 1.2), -4)
    return plume, episodes


def generate_sample_aqi(
    days: int = DEFAULT_DAYS,
    output_path: str | Path | None = None,
    start_date: str | date | datetime | None = None,
    metadata_path: str | Path | None = None,
) -> pd.DataFrame:
    config = load_config()
    if days < MIN_SAMPLE_DAYS or days > MAX_SAMPLE_DAYS:
        raise ValueError(f"days must be between {MIN_SAMPLE_DAYS} and {MAX_SAMPLE_DAYS}")
    rng = np.random.default_rng(int(config["random_state"]))
    if start_date is None:
        start_at = datetime.combine(_end_date(config) - timedelta(days=days - 1), time.min)
    else:
        start_at = pd.to_datetime(start_date).to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)
    timestamps = pd.date_range(start_at, periods=days * 24, freq="h")
    n = len(timestamps)
    hours = timestamps.hour.to_numpy(dtype=float)
    weekend = timestamps.day_of_week.to_numpy() >= 5
    pad = max(TRANSPORT_LAG_HOURS.values())
    plume, _ = _plume(rng, n, pad)

    commute = 7 * np.exp(-((hours - 8) / 2.0) ** 2) + 6 * np.exp(-((hours - 18.5) / 2.5) ** 2)
    commute = np.where(weekend, commute * 0.55, commute)
    sun = np.clip(np.sin((hours - 7) / 13 * np.pi), 0, None)

    event_rows: list[dict[str, object]] = []
    event_starts = np.sort(rng.choice(np.arange(24, n - 6), size=LOCAL_EVENTS, replace=False))
    event_sites = rng.choice([s[0] for s in SITES], size=LOCAL_EVENTS)
    frames = []
    for site_name, county, background, gain in SITES:
        wind = np.clip(2.6 + 1.1 * sun + _ar1(rng, n, 0.9, 0.35), 0.3, 9)
        lag = TRANSPORT_LAG_HOURS.get(site_name)
        regional = gain * plume[pad - lag : pad - lag + n] if lag is not None else np.zeros(n)
        ventilation = 1.0 + 0.22 * (2.6 - wind)
        pm25 = (background + commute + regional) * ventilation + _ar1(rng, n, 0.8, 2.0)
        co = 0.25 + 0.035 * commute + 0.006 * pm25 + rng.normal(0, 0.03, n)
        pm10 = pm25 * rng.normal(1.65, 0.08, n) + rng.normal(0, 3, n)

        for start, site in zip(event_starts, event_sites):
            if site != site_name:
                continue
            duration = int(rng.integers(2, 5))
            magnitude = rng.uniform(32, 55)
            shape = np.array([0.7, 1.0, 0.85, 0.6][:duration])
            window = slice(int(start), int(start) + duration)
            pm25[window] += magnitude * shape
            pm10[window] += magnitude * 1.8 * shape
            co[window] += 0.5 * shape
            event_rows.append(
                {
                    "site_name": site_name,
                    "start": timestamps[int(start)],
                    "end": timestamps[int(start) + duration - 1],
                    "peak_pm25_added": round(float(magnitude), 1),
                    "kind": "local_emission",
                }
            )

        o3 = np.clip(18 + 38 * sun - 0.12 * pm25 + rng.normal(0, 4, n), 2, 140)
        pm25 = np.clip(pm25, 1, 300)
        pm10 = np.clip(pm10, 3, 500)
        frame = pd.DataFrame(
            {
                "datetime": timestamps,
                "site_name": site_name,
                "county": county,
                "pm25": np.round(pm25, 1),
                "pm10": np.round(pm10, 1),
                "o3": np.round(o3, 1),
                "co": np.round(np.clip(co, 0.05, 5), 3),
                "wind_speed": np.round(wind, 2),
                "wind_directions": np.round((rng.normal(30, 25, n) if lag is not None else rng.normal(90, 40, n)) % 360, 1),
            }
        )
        frame["aqi"] = [round(aqi_scale.aqi(a, b, c), 1) for a, b, c in zip(frame.pm25, frame.pm10, frame.o3)]
        frames.append(frame)

    frame = pd.concat(frames, ignore_index=True)
    frame = frame[["datetime", "site_name", "county", "aqi", "pm25", "pm10", "o3", "co", "wind_speed", "wind_directions"]]
    missing_columns = ["pm25", "pm10", "o3", "co", "wind_speed"]
    missing = rng.random((len(frame), len(missing_columns))) < MISSING_RATE
    for idx, column in enumerate(missing_columns):
        frame.loc[missing[:, idx], column] = np.nan

    out = Path(output_path) if output_path is not None else resolve_path(config, "data.sample_file")
    write_csv(frame, out, index=False, encoding="utf-8")
    events = pd.DataFrame(event_rows).sort_values(["start", "site_name"]).reset_index(drop=True)
    write_csv(events, out.with_name("injected_events.csv"), index=False, encoding="utf-8")
    _write_sample_metadata(config, frame, out, metadata_path, generated_at=timestamps[-1])
    return frame


def _write_sample_metadata(config: dict, frame: pd.DataFrame, data_path: Path, metadata_path: str | Path | None, generated_at: pd.Timestamp) -> None:
    summary = frame_summary(frame)
    # Use the data's own end time so metadata is as reproducible as the data.
    stamp = generated_at.tz_localize("Asia/Taipei").tz_convert("UTC").isoformat().replace("+00:00", "Z")
    metadata = build_source_metadata(
        provider="sample_generator",
        mode="sample",
        status="success",
        row_count=summary["row_count"],
        datetime_range=summary["datetime_range"],
        schema_columns=summary["schema_columns"],
        schema_hash=summary["schema_sha256"],
        requested_at_utc=stamp,
        fetched_at_utc=stamp,
        data_file_sha256=file_sha256(data_path),
    )
    reports = config.get("reports", {})
    target = Path(metadata_path) if metadata_path is not None else (
        resolve_path(config, "reports.source_metadata_file") if "source_metadata_file" in reports else project_path("reports/metrics/source_metadata.json")
    )
    write_source_metadata(target, metadata)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--start-date", default=None, help="Optional start date, for example 2026-06-01.")
    parser.add_argument("--metadata", default=None)
    args = parser.parse_args()
    frame = generate_sample_aqi(days=args.days, start_date=args.start_date, metadata_path=args.metadata)
    print(f"Generated {len(frame):,} rows at data/sample/sample_aqi.csv")


if __name__ == "__main__":
    main()
