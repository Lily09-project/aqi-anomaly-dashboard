"""Compare ways of turning the ridge point forecast into P10/P50/P90.

Backs the choice documented in docs/METHODS.md. Reads the cleaned hourly file
written by ``run_all.py`` and scores each candidate on the pipeline's own
time-ordered train / calibration / test split, plus rolling re-splits of
earlier prefixes of the data. Prefixes of at most 85% of the history end
before the final test window starts, so they can inform the choice of method
without touching the test set.

    python run_all.py --mode api --require-api
    python scripts/compare_interval_methods.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.analytics import forecast, propagation  # noqa: E402
from src.analytics.panel import build_panels  # noqa: E402
from src.analytics.ridge import fit_ridge  # noqa: E402
from src.utils import load_config, resolve_path  # noqa: E402

LEVEL = forecast.INTERVAL_LEVEL
RECENT_HOURS = 72
PRE_TEST_FOLDS = (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85)
LABELS = {
    "median_shift": "(a) 加校準殘差中位數，區間為殘差 10%/90% 分位數（舊法）",
    "no_shift": "(b) 不位移，區間為殘差 10%/90% 分位數",
    "symmetric": "(c) 不位移，對稱分割式保形區間（採用）",
    "half_shift": "(d1) 位移量減半，區間同 (b)",
    "recent_shift": f"(d2) 只用校準期最後 {RECENT_HOURS} 小時估位移，區間同 (b)",
}


def candidates(residuals: np.ndarray, origins: pd.Series) -> dict[str, tuple[float, float, float]]:
    """Offsets (P50, lower, upper) from the raw point forecast for every method."""
    q10, q50, q90 = (float(np.quantile(residuals, q)) for q in ((1 - LEVEL) / 2, 0.5, (1 + LEVEL) / 2))
    half = forecast.conformal_half_width(residuals, LEVEL)
    recent = residuals[(origins > origins.max() - pd.Timedelta(hours=RECENT_HOURS)).to_numpy()]
    return {
        "median_shift": (q50, q10, q90),
        "no_shift": (0.0, q10, q90),
        "symmetric": (0.0, -half, half),
        "half_shift": (q50 / 2, q10, q90),
        "recent_shift": (float(np.median(recent)), q10, q90),
    }


def score(panels: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """One row per horizon and method, evaluated on the last 15% of ``panels``."""
    aqi = panels["aqi"]
    train_end, calibration_end = forecast.split_times(aqi.index)
    links, _ = propagation.lead_lag_links(panels["pm25"].loc[:train_end])
    upstream = {station: link.upstream for station, link in propagation.nearest_upstream(links).items()}
    climatology = forecast._climatology(aqi, train_end)
    features = [*forecast.FEATURE_NAMES, forecast.UPSTREAM_FEATURE]
    rows = []
    for horizon in forecast.HORIZONS:
        table = forecast.design_matrix(panels, climatology, horizon, upstream).dropna()
        target_time = table["origin"] + pd.Timedelta(hours=horizon)
        train = table[target_time <= train_end]
        calibration = table[(table["origin"] > train_end) & (target_time <= calibration_end)]
        test = table[table["origin"] > calibration_end]
        model = fit_ridge(train[features].to_numpy(), train["target"].to_numpy(), alpha=1.0)
        residuals = calibration["target"].to_numpy() - model.predict(calibration[features].to_numpy())
        point, actual = model.predict(test[features].to_numpy()), test["target"].to_numpy()
        for method, (shift, low, high) in candidates(residuals, calibration["origin"]).items():
            lower, upper = point + low, point + high
            miss = np.maximum(lower - actual, 0) + np.maximum(actual - upper, 0)
            rows.append({
                "h": horizon,
                "method": method,
                "mae": float(np.abs(actual - point - shift).mean()),
                "persistence": float(np.abs(actual - test["aqi_now"].to_numpy()).mean()),
                "climatology": float(np.abs(actual - test["clim_target"].to_numpy()).mean()),
                "coverage": float((miss == 0).mean()),
                "width": high - low,
                # Interval (Winkler) score: width plus 2/α times the miss distance; lower is better.
                "interval_score": float((upper - lower + 2 / (1 - LEVEL) * miss).mean()),
            })
    return pd.DataFrame(rows)


def summary(scores: pd.DataFrame) -> pd.DataFrame:
    """Per-method means over horizons, with the number of horizons beating each baseline."""
    longest = int(scores["h"].max())
    rows = {}
    for method, group in scores.groupby("method", sort=False):
        rows[method] = {
            "MAE 平均": group["mae"].mean(),
            f"MAE {longest}h": float(group.loc[group["h"] == longest, "mae"].iloc[0]),
            "贏持續性": int((group["mae"] < group["persistence"]).sum()),
            "贏氣候值": int((group["mae"] < group["climatology"]).sum()),
            "覆蓋率": group["coverage"].mean(),
            "覆蓋率最低": group["coverage"].min(),
            "覆蓋率最高": group["coverage"].max(),
            "區間寬度": group["width"].mean(),
            "區間分數": group["interval_score"].mean(),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def rolling(panels: dict[str, pd.DataFrame], folds: tuple[float, ...] = PRE_TEST_FOLDS) -> pd.DataFrame:
    """Mean scores over re-splits of prefixes that stop before the final test window."""
    length = len(panels["aqi"])
    parts = [score({name: panel.iloc[: int(length * fold)] for name, panel in panels.items()}).assign(fold=fold) for fold in folds]
    per_fold = pd.concat(parts, ignore_index=True).groupby(["method", "fold"], sort=False)[["mae", "coverage", "width", "interval_score"]].mean()
    rows = {}
    for method, group in per_fold.groupby(level="method", sort=False):
        rows[method] = {
            "MAE 平均": group["mae"].mean(),
            "覆蓋率": group["coverage"].mean(),
            "覆蓋率離目標": float((group["coverage"] - LEVEL).abs().mean()),
            "區間寬度": group["width"].mean(),
            "區間分數": group["interval_score"].mean(),
        }
    return pd.DataFrame.from_dict(rows, orient="index")


def _cell(column: str, value: float) -> str:
    if column.startswith("贏"):
        return f"{int(value)}/{len(forecast.HORIZONS)}"
    return f"{value:.1%}" if "覆蓋率" in column else f"{value:.2f}"


def markdown(table: pd.DataFrame) -> str:
    lines = ["| 方法 | " + " | ".join(table.columns) + " |", "| --- |" + " ---: |" * len(table.columns)]
    for name, row in table.iterrows():
        lines.append(f"| {LABELS.get(str(name), name)} | " + " | ".join(_cell(str(c), float(v)) for c, v in row.items()) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cleaned", type=Path, default=None, help="cleaned hourly CSV (default: the pipeline's cleaned file)")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cleaned = pd.read_csv(args.cleaned or resolve_path(load_config(), "data.cleaned_file"))
    panels = build_panels(cleaned, causal=True)
    index = panels["aqi"].index
    train_end, calibration_end = forecast.split_times(index)
    final = score(panels)
    reference = final[final["method"] == "symmetric"]
    print(f"資料 {index[0]:%Y-%m-%d %H:%M} 至 {index[-1]:%Y-%m-%d %H:%M}；訓練至 {train_end:%Y-%m-%d %H:%M}，校準至 {calibration_end:%Y-%m-%d %H:%M}，其後為測試。")
    print(f"測試期基準 MAE 平均：持續性 {reference['persistence'].mean():.2f}，氣候值 {reference['climatology'].mean():.2f}；目標覆蓋率 {LEVEL:.0%}。\n")
    print("最終切分（測試期，只用來確認）\n")
    print(markdown(summary(final)))
    print(f"\n滾動重切（資料前 {'、'.join(f'{fold:.0%}' for fold in PRE_TEST_FOLDS)}，都在最終測試期開始前結束；{len(PRE_TEST_FOLDS)} 次平均）\n")
    print(markdown(rolling(panels)))


if __name__ == "__main__":
    main()
