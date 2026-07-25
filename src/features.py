from __future__ import annotations

import argparse

import pandas as pd

from src.utils import ensure_parent, load_config, resolve_path


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
