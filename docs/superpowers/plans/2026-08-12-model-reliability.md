# Model Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Select the predictor from pre-test rolling-origin evidence, add a leakage-safe station-hour context feature, and report subgroup reliability.

**Architecture:** Feature generation owns historical-only context; training owns candidate selection and final fit; evaluation helpers own per-station, AQI-band, baseline-improvement, and interval-coverage reports.

**Tech Stack:** Python 3.12, pandas, NumPy, scikit-learn, pytest

## Global Constraints

- Final-test targets cannot affect feature design, model selection, tuning, or interval calibration.
- History features must be isolated by station and use only earlier timestamps.
- Retain Moving Average, Linear Regression, and Random Forest.
- Select a learned model only when pre-test rolling-origin RMSE beats Moving Average.
- Every subgroup metric includes row count.

---

### Task 1: Leakage-Safe Station-Hour Baseline Feature

**Files:**
- Modify: `src/features.py`
- Modify: `config.yaml`
- Modify: `tests/test_features.py`

**Interfaces:**
- Produces: `historical_station_hour_baseline(frame) -> pd.Series`

- [x] Write failing tests proving future mutation invariance, station isolation, and fallback order.
- [x] Confirm RED.
- [x] Implement a chronological one-pass history accumulator using only values observed before each timestamp. Use station-hour median, then station median, then global median.
- [x] Add `station_hour_baseline_aqi` to configured feature columns.
- [x] Run feature and leakage tests, then commit with `git commit -m "feat: add leakage-safe station-hour baseline feature"`.

### Task 2: Rolling-Origin Model Selection

**Files:**
- Modify: `src/train_predictor.py`
- Modify: `tests/test_model_training.py`

**Interfaces:**
- Produces: `select_model_from_backtest(backtest, available_models) -> str`

- [x] Write failing tests where linear regression wins aggregate RMSE and where no learned model beats Moving Average.
- [x] Confirm RED.
- [x] Implement deterministic selection with RMSE then model-name tie-break; return `moving_average` when learned candidates do not beat it.
- [x] Ensure calibration residuals correspond to the selected candidate and remain pre-test.
- [x] Support baseline selection through a serializable `MovingAverageModel` that predicts from rolling/lag columns.
- [x] Run focused training tests and commit with `git commit -m "feat: select predictor from rolling backtests"`.

### Task 3: Subgroup Reliability Metrics

**Files:**
- Create: `src/model_reliability.py`
- Create: `tests/test_model_reliability.py`
- Modify: `src/train_predictor.py`

**Interfaces:**
- Produces: `build_reliability_report(predictions, baseline_col, prediction_col) -> dict[str, Any]`

- [x] Write failing tests for per-station metrics, AQI bands, baseline improvement, worst station, and row counts.
- [x] Confirm RED.
- [x] Implement finite-row filtering and safe R2 for constant or one-row groups.
- [x] Add report under `predictor_metrics.json["reliability"]`.
- [x] Run focused tests and commit with `git commit -m "feat: report predictor reliability by station and AQI band"`.

### Task 4: Station-Level Interval Coverage

**Files:**
- Modify: `src/forecast_confidence.py`
- Modify: `tests/test_forecast_confidence.py`
- Modify: `src/train_predictor.py`

**Interfaces:**
- Produces: `build_group_coverage(frame, group_col, levels) -> dict[str, Any]`

- [x] Write failing coverage tests with known 80%/95% inclusion outcomes and small groups.
- [x] Confirm RED.
- [x] Implement per-group coverage, mean width, and rows without changing interval widths.
- [x] Store results under `forecast_confidence.json["station_coverage"]`.
- [x] Run focused tests and commit with `git commit -m "feat: report forecast coverage by station"`.

### Task 5: Dashboard, Documentation, and Full Verification

**Files:**
- Modify: `src/dashboard/pages/metrics.py`
- Modify: `README.md`
- Modify: `tests/test_dashboard_pages.py`

**Interfaces:**
- Consumes: reliability and station coverage metric contracts from Tasks 3-4

- [x] Write failing UI tests requiring worst-station, baseline-improvement, and station-coverage summaries without raw JSON.
- [x] Confirm RED.
- [x] Render concise tables with explicit sample counts and limitations.
- [x] Update README model selection, leakage prevention, evaluation, limitations, resume bullet, and interview script.
- [x] Run `python run_all.py --mode sample`, smoke, full pytest, pip check, pip-audit, secret scan, artifact tracking check, diff check, desktop review, 390px review, and console inspection.
- [x] Commit with `git commit -m "feat: complete leakage-safe model reliability reporting"`.
