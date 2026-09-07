from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.source_metadata import build_source_metadata, file_sha256, frame_summary, write_source_metadata
from src.utils import load_config, project_path, resolve_path, write_csv


SITES = [
    ("松山測站", "臺北市", 55, 18),
    ("板橋測站", "新北市", 62, 20),
    ("桃園測站", "桃園市", 68, 22),
    ("西屯測站", "臺中市", 70, 24),
    ("安南測站", "臺南市", 76, 27),
    ("前金測站", "高雄市", 86, 31),
    ("宜蘭測站", "宜蘭縣", 42, 13),
    ("花蓮測站", "花蓮縣", 38, 12),
]


MIN_SAMPLE_DAYS = 1
MAX_SAMPLE_DAYS = 366


def _default_start_date(days: int) -> datetime:
    return datetime.combine(date.today() - timedelta(days=days - 1), time.min)


def _metadata_target(config: dict, metadata_path: str | Path | None) -> Path:
    if metadata_path is not None:
        return Path(metadata_path)
    reports = config.get("reports", {})
    configured = reports.get("source_metadata_file", "reports/metrics/source_metadata.json")
    return resolve_path(config, "reports.source_metadata_file") if "source_metadata_file" in reports else project_path(configured)


def _write_sample_metadata(
    config: dict,
    frame: pd.DataFrame,
    data_path: str | Path,
    metadata_path: str | Path | None = None,
) -> None:
    summary = frame_summary(frame)
    metadata = build_source_metadata(
        provider="sample_generator",
        mode="sample",
        status="success",
        row_count=summary["row_count"],
        datetime_range=summary["datetime_range"],
        schema_columns=summary["schema_columns"],
        schema_hash=summary["schema_sha256"],
        requested_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        fetched_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        data_file_sha256=file_sha256(data_path),
    )
    write_source_metadata(_metadata_target(config, metadata_path), metadata)


def generate_sample_aqi(
    days: int = 30,
    output_path: str | Path | None = None,
    start_date: str | date | datetime | None = None,
    metadata_path: str | Path | None = None,
) -> pd.DataFrame:
    config = load_config()
    if days < MIN_SAMPLE_DAYS or days > MAX_SAMPLE_DAYS:
        raise ValueError(f"days must be between {MIN_SAMPLE_DAYS} and {MAX_SAMPLE_DAYS}")
    rng = np.random.default_rng(config["random_state"])
    if start_date is None:
        start_at = _default_start_date(days)
    else:
        start_at = pd.to_datetime(start_date).to_pydatetime().replace(hour=0, minute=0, second=0, microsecond=0)
    timestamps = pd.date_range(start_at, periods=days * 24, freq="h")
    sample_count = len(timestamps)
    positions = np.arange(sample_count)
    hours = timestamps.hour.to_numpy(dtype=float)
    weekdays = timestamps.dayofweek.to_numpy()
    commute = 12 * np.exp(-((hours - 8) / 2.5) ** 2) + 10 * np.exp(-((hours - 18) / 3) ** 2)
    weekend_offset = np.where(weekdays >= 5, -7.0, 0.0)
    seasonal_wave = 6 * np.sin(positions / 24 / 5 * 2 * np.pi)
    site_frames: list[pd.DataFrame] = []

    for site_name, county, base_aqi, base_pm25 in SITES:
        aqi = base_aqi + rng.normal(0, 3) + commute + weekend_offset + seasonal_wave + rng.normal(0, 5, sample_count)

        if site_name in {"前金測站", "安南測站"}:
            event_mask = np.isin(hours, (9, 10, 19, 20)) & (positions % 47 == 0)
            aqi[event_mask] += rng.uniform(45, 80, int(event_mask.sum()))
        if site_name == "松山測站":
            event_mask = positions % 113 == 0
            aqi[event_mask] += rng.uniform(35, 60, int(event_mask.sum()))

        pm25 = base_pm25 + aqi * 0.24 + rng.normal(0, 3, sample_count)
        pm10 = pm25 * rng.uniform(1.45, 2.0, sample_count) + rng.normal(0, 4, sample_count)
        o3 = np.maximum(8, 30 + 0.25 * aqi + 9 * np.sin((hours - 13) / 24 * 2 * np.pi) + rng.normal(0, 4, sample_count))
        co = np.maximum(0.1, 0.28 + aqi / 210 + rng.normal(0, 0.05, sample_count))
        wind_speed = np.maximum(0.2, 3.2 - aqi / 75 + rng.normal(0, 0.7, sample_count))
        wind_directions = (rng.normal(180, 55, sample_count) + positions * 3) % 360

        site_frames.append(
            pd.DataFrame(
                {
                    "datetime": timestamps,
                    "site_name": site_name,
                    "county": county,
                    "aqi": np.round(np.clip(aqi, 12, 230), 1),
                    "pm25": np.round(np.clip(pm25, 2, 95), 1),
                    "pm10": np.round(np.clip(pm10, 5, 160), 1),
                    "o3": np.round(np.clip(o3, 1, 125), 1),
                    "co": np.round(np.clip(co, 0.1, 2.8), 3),
                    "wind_speed": np.round(np.clip(wind_speed, 0.2, 8), 2),
                    "wind_directions": np.round(wind_directions, 1),
                }
            )
        )

    frame = pd.concat(site_frames, ignore_index=True)
    missing_columns = ["pm25", "pm10", "o3", "co", "wind_speed"]
    missing_mask = rng.random((len(frame), len(missing_columns))) < 0.006
    for idx, col in enumerate(missing_columns):
        frame.loc[missing_mask[:, idx], col] = np.nan
    if output_path is None:
        output_path = resolve_path(config, "data.sample_file")
    out = Path(output_path)
    write_csv(frame, out, index=False, encoding="utf-8")
    _write_sample_metadata(config, frame, out, metadata_path)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--start-date", default=None, help="Optional start date, for example 2026-06-01.")
    parser.add_argument("--metadata", default=None)
    args = parser.parse_args()
    frame = generate_sample_aqi(days=args.days, start_date=args.start_date, metadata_path=args.metadata)
    print(f"Generated {len(frame):,} rows at data/sample/sample_aqi.csv")


if __name__ == "__main__":
    main()
