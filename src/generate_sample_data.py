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
    rows: list[dict[str, object]] = []

    for site_name, county, base_aqi, base_pm25 in SITES:
        site_shift = rng.normal(0, 3)
        for i, ts in enumerate(timestamps):
            hour = ts.hour
            weekday = ts.dayofweek
            commute = 12 * np.exp(-((hour - 8) / 2.5) ** 2) + 10 * np.exp(-((hour - 18) / 3) ** 2)
            weekend_offset = -7 if weekday >= 5 else 0
            seasonal_wave = 6 * np.sin(i / 24 / 5 * 2 * np.pi)
            noise = rng.normal(0, 5)
            aqi = base_aqi + site_shift + commute + weekend_offset + seasonal_wave + noise

            if site_name in {"前金測站", "安南測站"} and hour in {9, 10, 19, 20} and i % 47 == 0:
                aqi += rng.uniform(45, 80)
            if site_name == "松山測站" and i % 113 == 0:
                aqi += rng.uniform(35, 60)

            pm25 = base_pm25 + aqi * 0.24 + rng.normal(0, 3)
            pm10 = pm25 * rng.uniform(1.45, 2.0) + rng.normal(0, 4)
            o3 = max(8, 30 + 0.25 * aqi + 9 * np.sin((hour - 13) / 24 * 2 * np.pi) + rng.normal(0, 4))
            co = max(0.1, 0.28 + aqi / 210 + rng.normal(0, 0.05))
            wind_speed = max(0.2, 3.2 - aqi / 75 + rng.normal(0, 0.7))
            wind_directions = float((rng.normal(180, 55) + i * 3) % 360)

            rows.append(
                {
                    "datetime": ts,
                    "site_name": site_name,
                    "county": county,
                    "aqi": round(float(np.clip(aqi, 12, 230)), 1),
                    "pm25": round(float(np.clip(pm25, 2, 95)), 1),
                    "pm10": round(float(np.clip(pm10, 5, 160)), 1),
                    "o3": round(float(np.clip(o3, 1, 125)), 1),
                    "co": round(float(np.clip(co, 0.1, 2.8)), 3),
                    "wind_speed": round(float(np.clip(wind_speed, 0.2, 8)), 2),
                    "wind_directions": round(wind_directions, 1),
                }
            )

    frame = pd.DataFrame(rows)
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
