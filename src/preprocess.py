from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from src.app_helpers import add_display_columns
from src.fetch_aqi_data import ALIASES
from src.utils import latest_csv, load_config, project_path, resolve_path, write_csv


NUMERIC_COLUMNS = ["aqi", "pm25", "pm10", "o3", "co", "wind_speed", "wind_directions"]
REQUIRED_COLUMNS = ["datetime", "site_name", "county", *NUMERIC_COLUMNS]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename_map: dict[str, str] = {}
    lower_lookup = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    for canonical, aliases in ALIASES.items():
        keys = [canonical, *aliases]
        for key in keys:
            normalized = key.lower().replace(" ", "").replace("_", "")
            if normalized in lower_lookup:
                rename_map[lower_lookup[normalized]] = canonical
                break
    return df.rename(columns=rename_map)


def _input_path(config: dict, mode: str) -> Path:
    if mode == "sample":
        return resolve_path(config, "data.sample_file")
    latest = latest_csv(project_path(config["data"]["raw_dir"]))
    return latest or resolve_path(config, "data.sample_file")


def _is_verified_api_source(mode: str, source_metadata: Mapping[str, Any] | None) -> bool:
    if mode != "api":
        return False
    if source_metadata is None:
        return True
    return (
        source_metadata.get("status") == "success"
        and source_metadata.get("data_source") == "API Data"
        and source_metadata.get("is_simulated_data") is False
    )


def preprocess(
    mode: str = "sample",
    input_path: str | Path | None = None,
    source_metadata: Mapping[str, Any] | None = None,
) -> pd.DataFrame:
    config = load_config()
    src = Path(input_path) if input_path else _input_path(config, mode)
    if not src.exists():
        raise FileNotFoundError(f"Input data not found: {src}")

    df = normalize_columns(pd.read_csv(src))
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns after alias mapping: {missing}")

    df = df[REQUIRED_COLUMNS].copy()
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df["site_name"] = df["site_name"].astype(str).str.strip()
    df["county"] = df["county"].astype(str).str.strip()

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["datetime", "site_name"]).sort_values(["site_name", "datetime"])
    for col in NUMERIC_COLUMNS:
        df[col] = df.groupby("site_name", sort=False)[col].ffill()

    df = df.dropna(subset=NUMERIC_COLUMNS)
    df = df.drop_duplicates(["site_name", "datetime"]).reset_index(drop=True)
    df["data_source"] = "API Data" if _is_verified_api_source(mode, source_metadata) else "Sample Data"
    df = add_display_columns(df)
    out = resolve_path(config, "data.cleaned_file")
    write_csv(df, out, index=False, encoding="utf-8")
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["sample", "api"], default="sample")
    args = parser.parse_args()
    df = preprocess(mode=args.mode)
    print(f"Preprocessed {len(df):,} rows at data/processed/aqi_cleaned.csv")


if __name__ == "__main__":
    main()