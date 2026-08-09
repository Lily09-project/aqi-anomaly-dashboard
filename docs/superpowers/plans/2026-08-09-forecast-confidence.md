# Forecast Confidence and AQI Threshold Watch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add leakage-safe empirical prediction intervals and transparent AQI threshold monitoring to the next-hour forecast workflow and Dashboard.

**Architecture:** A focused backend module calibrates model-agnostic intervals from rolling-origin out-of-fold residuals. Predictor training writes enriched predictions and a metrics artifact; Streamlit only reads and presents those outputs with graceful fallback.

**Tech Stack:** Python 3.12, pandas, NumPy, scikit-learn, Plotly, Streamlit, pytest.

## Global Constraints

- Calibration rows must predate the final-test split.
- Final-test targets may evaluate coverage but may not calibrate quantiles.
- 95% intervals must contain 80% intervals; AQI lower bounds must be non-negative.
- UI must remain Traditional Chinese, high contrast, responsive, and free of raw JSON or code output.
- Sample Data must remain clearly identified as simulated data.

---

### Task 1: Confidence Calibration Core

**Files:**
- Create: `src/forecast_confidence.py`
- Create: `tests/test_forecast_confidence.py`

**Interfaces:**
- Produces: `calibrate_interval_widths(residuals, levels) -> dict[str, float]`
- Produces: `apply_prediction_intervals(frame, prediction_col, widths) -> pd.DataFrame`
- Produces: `build_confidence_metrics(frame, widths, calibration_rows) -> dict[str, object]`
- Produces: `classify_threshold_watch(frame, thresholds) -> pd.DataFrame`

- [ ] **Step 1: Write failing calibration and interval tests**

```python
def test_calibration_is_monotonic_and_intervals_are_non_negative():
    widths = calibrate_interval_widths([1, 2, 3, 4, 8], levels=(0.8, 0.95))
    result = apply_prediction_intervals(pd.DataFrame({"prediction": [2.0, 100.0]}), "prediction", widths)
    assert widths["95"] >= widths["80"] >= 0
    assert (result["lower_95_aqi"] >= 0).all()
    assert (result["lower_95_aqi"] <= result["lower_80_aqi"]).all()
    assert (result["upper_95_aqi"] >= result["upper_80_aqi"]).all()
```

- [ ] **Step 2: Run the focused test and confirm import failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_forecast_confidence.py -q`

Expected: FAIL because `src.forecast_confidence` does not exist.

- [ ] **Step 3: Implement finite-sample conformal quantiles and interval application**

Use the higher empirical quantile with rank `ceil((n + 1) * level)`, capped at `n`, and reject fewer than two finite residuals.

- [ ] **Step 4: Add failing threshold-watch and metrics tests**

```python
def test_threshold_watch_distinguishes_80_and_95_percent_crossings():
    frame = pd.DataFrame({
        "predicted_next_hour_aqi": [48.0, 48.0, 40.0],
        "upper_80_aqi": [52.0, 49.0, 45.0],
        "upper_95_aqi": [55.0, 53.0, 48.0],
    })
    result = classify_threshold_watch(frame, [50, 100])
    assert result["threshold_watch_level"].tolist() == ["跨級關注", "不確定性關注", "區間穩定"]
```

- [ ] **Step 5: Implement classification and empirical coverage metrics, then run focused tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_forecast_confidence.py -q`

Expected: PASS.

### Task 2: Leakage-Safe Training Integration

**Files:**
- Modify: `src/train_predictor.py`
- Modify: `config.yaml`
- Modify: `tests/test_model_training.py`

**Interfaces:**
- Extends: `rolling_origin_backtest(..., collect_residuals_for: str | None = None)` with calibration residuals and period metadata.
- Writes: enriched `data/processed/aqi_predictions.csv`.
- Writes: `reports/metrics/forecast_confidence.json`.

- [ ] **Step 1: Write failing integration assertions**

Require interval columns, a non-empty metrics file, monotonic widths, and `calibration_end < final_test_start`.

- [ ] **Step 2: Run the focused training test and confirm missing outputs**

Run: `.venv\Scripts\python.exe -m pytest tests/test_model_training.py -q`

Expected: FAIL because confidence outputs are absent.

- [ ] **Step 3: Collect selected-model rolling residuals without changing model selection**

Each fold fits on earlier rows and appends `abs(actual - predicted)` for the already selected model. Persist fold boundaries in confidence metrics.

- [ ] **Step 4: Calibrate, apply, classify, and write metrics**

Read interval levels and thresholds from `config.yaml`; append interval/watch columns before writing predictions.

- [ ] **Step 5: Run model training and leakage tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_model_training.py tests/test_features.py -q`

Expected: PASS.

### Task 3: Pipeline Contracts and Smoke Checks

**Files:**
- Modify: `run_all.py`
- Modify: `src/smoke_test.py`
- Modify: `src/evaluate.py`
- Modify: `tests/test_evaluate.py`
- Modify: `tests/test_run_all.py`

**Interfaces:**
- Adds required artifact: `reports/metrics/forecast_confidence.json`.
- Adds confidence summary to `evaluation_summary.json`.

- [ ] **Step 1: Write failing artifact and summary assertions**
- [ ] **Step 2: Run evaluate and run-all tests to verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_evaluate.py tests/test_run_all.py -q`

- [ ] **Step 3: Add outputs to summary, evaluation, and smoke contracts**
- [ ] **Step 4: Re-run focused tests and smoke test**

Run: `.venv\Scripts\python.exe src\smoke_test.py`

Expected: `Smoke test passed.`

### Task 4: Prediction Dashboard Experience

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app_import.py`

**Interfaces:**
- Produces: `_confidence_summary_table(metrics) -> pd.DataFrame`
- Produces: `_threshold_watch_table(predictions) -> pd.DataFrame`

- [ ] **Step 1: Write failing helper tests for flattened metrics and sorted watch rows**
- [ ] **Step 2: Run app import tests and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/test_app_import.py -q`

- [ ] **Step 3: Implement helpers and Prediction-tab rendering**

Add an 80% Plotly band using two traces with `fill="tonexty"`, reliability metrics, watch table, and a limitation caption. Keep missing-output fallback neutral.

- [ ] **Step 4: Run app import tests**

Expected: PASS.

### Task 5: Documentation and Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document calibration data flow, outputs, limitations, interview value, and Demo steps**
- [ ] **Step 2: Run the full one-click validation**

Run: `cmd.exe /d /c "run_project.bat --validate"`

Expected: pipeline, smoke test, and pytest all pass.

- [ ] **Step 3: Run dependency, diff, and credential checks**

Run: `.venv\Scripts\python.exe -m pip check`

Run: `git diff --check`

Run: `rg -n --hidden --glob '!/.venv/**' --glob '!/.git/**' '(?i)(api[_-]?key\s*[=:]|secret\s*[=:]|password\s*[=:]|token\s*[=:])' .`

- [ ] **Step 4: Verify desktop and 390px mobile layouts in a real browser**

Confirm the Prediction tab renders intervals and threshold watch without horizontal overflow, low-contrast text, raw JSON, raw HTML, traceback, or console errors.
