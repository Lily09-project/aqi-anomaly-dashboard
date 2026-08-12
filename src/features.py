from __future__ import annotations

import argparse
from collections import defaultdict
from statistics import median

import pandas as pd

from src.utils import ensure_parent, load_config, resolve_path


def historical_station_hour_baseline(frame: pd.DataFrame) -> pd.Series:
    """Return station-hour medians derived strictly from earlier timestamps."""
    required = {"datetime", "site_name", "aqi"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("Missing baseline columns: " + ", ".join(missing))

    working = frame[["datetime", "site_name", "aqi"]].copy()
    working["datetime"] = pd.to_datetime(working["datetime"], errors="coerce")
    working["aqi"] = pd.to_numeric(working["aqi"], errors="coerce")
    working["_position"] = range(len(working))
    working = working.sort_values(["datetime", "_position"], kind="stable")

    baselines = [float("nan")] * len(working)
    station_hour_history: dict[tuple[str, int], list[float]] = defaultdict(list)
    station_history: dict[str, list[float]] = defaultdict(list)
    global_history: list[float] = []

    for _, current_rows in working.groupby("datetime", sort=True, dropna=False):
        records = current_rows.to_dict(orient="records")
        for row in records:
            if pd.isna(row["datetime"]) or pd.isna(row["aqi"]):
                continue
            site_name = str(row["site_name"])
            hour = int(row["datetime"].hour)
            history = station_hour_history[(site_name, hour)]
            if history:
                baseline = median(history)
            elif station_history[site_name]:
                baseline = median(station_history[site_name])
            elif global_history:
                baseline = median(global_history)
            else:
                continue
            baselines[int(row["_position"])] = float(baseline)

        # A timestamp becomes history only after every baseline at that timestamp is fixed.
        for row in records:
            if pd.isna(row["datetime"]) or pd.isna(row["aqi"]):
                continue
            site_name = str(row["site_name"])
            value = float(row["aqi"])
            station_hour_history[(site_name, int(row["datetime"].hour))].append(value)
            station_history[site_name].append(value)
            global_history.append(value)

    return pd.Series(baselines, index=frame.index, name="station_hour_baseline_aqi")

def build_features() -> pd.DataFrame:
    config = load_config()
    cleaned_path = resolve_path(config, "data.cleaned_file")
    if not cleaned_path.exists():
        raise FileNotFoundError("Run preprocess.py before feature engineering.")

    df = pd.read_csv(cleaned_path, parse_dates=["datetime"])
    df = df.sort_values(["site_name", "datetime"]).reset_index(drop=True)
    df["hour"] = df["datetime"].dt.hour
    df["day_of_week"] = df["datetime"].dt.dayofweek
    df["month"] = df["datetime"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["station_hour_baseline_aqi"] = historical_station_hour_baseline(df)

    grouped = df.groupby("site_name", group_keys=False)
    df["lag_1_aqi"] = grouped["aqi"].shift(1)
    df["lag_3_aqi"] = grouped["aqi"].shift(3)
    df["rolling_3h_aqi"] = grouped["aqi"].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    df["rolling_6h_aqi"] = grouped["aqi"].transform(lambda s: s.shift(1).rolling(6, min_periods=1).mean())
    df["rolling_12h_aqi"] = grouped["aqi"].transform(lambda s: s.shift(1).rolling(12, min_periods=1).mean())
    df["pm25_lag_1"] = grouped["pm25"].shift(1)
    df["pm25_rolling_3h"] = grouped["pm25"].transform(lambda s: s.shift(1).rolling(3, min_periods=1).mean())
    df["aqi_diff"] = grouped["aqi"].diff()
    df["pm25_diff"] = grouped["pm25"].diff()
    df["target_next_hour_aqi"] = grouped["aqi"].shift(-1)
    next_timestamp = grouped["datetime"].shift(-1)
    df.loc[next_timestamp - df["datetime"] != pd.Timedelta(hours=1), "target_next_hour_aqi"] = pd.NA
    df["target_aqi"] = df["target_next_hour_aqi"]

    feature_cols = config["train"]["feature_columns"]
    df = df.dropna(subset=[*feature_cols, "target_next_hour_aqi", "target_aqi"]).reset_index(drop=True)

    out = ensure_parent(resolve_path(config, "data.features_file"))
    df.to_csv(out, index=False, encoding="utf-8")
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    df = build_features()
    print(f"Built {len(df):,} feature rows at data/processed/aqi_features.csv")


if __name__ == "__main__":
    main()
