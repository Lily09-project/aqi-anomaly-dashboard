# Forecast Confidence and AQI Threshold Watch Design

## Goal

Add empirically calibrated uncertainty to the existing next-hour AQI forecast so the dashboard communicates a plausible range and flags stations whose range may cross an operational AQI threshold. This is a decision-support feature, not an official warning or a probabilistic health-risk estimate.

## Chosen Approach

Use model-agnostic split-conformal style intervals calibrated from rolling-origin out-of-fold absolute residuals. Every calibration prediction is produced by a model trained only on earlier timestamps. The later final test target is used only to report interval coverage and is never used to choose the interval width.

Alternatives were rejected for this iteration:

- Model drift monitoring has lower demonstration value while the project primarily uses simulated data.
- Recursive six-hour forecasts would compound error and require assumptions that the current feature set cannot defend.

## Architecture

`src/forecast_confidence.py` owns interval calibration, interval application, coverage metrics, and threshold-watch classification. It has no Streamlit dependency.

`src/train_predictor.py` collects rolling-origin residuals for the model selected on the chronological validation split, calibrates 80% and 95% interval widths, applies them to final-test predictions, and writes metrics. The existing model-selection and final-test boundaries remain unchanged.

`app.py` reads the generated columns and metrics. The Prediction tab renders an uncertainty ribbon, compact reliability metrics, and a threshold-watch table. Missing or legacy outputs degrade to an explanatory info state instead of crashing.

## Data Contract

`data/processed/aqi_predictions.csv` gains:

- `lower_80_aqi`, `upper_80_aqi`
- `lower_95_aqi`, `upper_95_aqi`
- `threshold_watch_level`
- `threshold_watch_reason`

`reports/metrics/forecast_confidence.json` contains:

- calibration source and row count
- 80% and 95% residual quantiles
- empirical final-test coverage and mean interval width
- configured AQI thresholds
- a limitation note stating that coverage is empirical and sample-data results are illustrative

AQI lower bounds are clipped to zero. Interval widths must be finite, non-negative, and monotonic: the 95% interval cannot be narrower than the 80% interval.

## Threshold Watch

The threshold policy uses configured AQI breakpoints 50, 100, 150, 200, and 300. A row is:

- `跨級關注` when the 80% interval crosses the next breakpoint above the point prediction.
- `不確定性關注` when only the 95% interval crosses that next breakpoint.
- `區間穩定` when neither interval crosses the next breakpoint.

The reason names the crossed breakpoint and interval level. This is deliberately transparent and does not invent a probability of exceedance.

## UI Design

Keep the existing industrial, high-contrast control-room direction. The Prediction tab adds one unframed section below Actual vs Predicted:

- A line chart with actual AQI, point prediction, and a subdued 80% uncertainty band.
- Four compact metrics: 80% coverage, 95% coverage, average 80% width, and calibration rows.
- A concise threshold-watch table sorted by watch severity, interval upper bound, and timestamp.
- A visible limitation caption explaining empirical coverage and sample-data limitations.

No nested cards, raw JSON, source code, or ambiguous red/green-only encoding is introduced. Labels and text retain the selected theme's validated contrast.

## Failure Handling

- Fewer than two calibration residuals raises a clear `ValueError` in the backend.
- Non-finite residuals are discarded before calibration.
- Missing confidence metrics or interval columns show a neutral rebuild instruction in the Dashboard.
- Empty filtered predictions show the existing empty-state message.

## Testing

- Unit tests prove quantile monotonicity, non-negative bounds, threshold classification, and deterministic metrics.
- A chronology test proves every calibration fold has `train_end < test_start` and the calibration end precedes final-test start.
- Pipeline tests require the new CSV columns and metrics file.
- App import tests cover table preparation and missing-output fallback helpers.
- Final verification runs the full sample pipeline, smoke test, pytest suite, dependency check, secret-pattern scan, and desktop/mobile browser checks.

## Scope

This iteration does not add multi-hour forecasting, probabilistic exceedance claims, external weather data, SHAP, alert delivery, or real-time scheduling.
