# Codebase Optimization Design

## Goal

Improve the AQI Dashboard in three independently verifiable stages: application architecture, Streamlit rerun performance, and leakage-safe model reliability. Preserve the current six-view user experience and all existing public behavior unless this specification explicitly changes it.

## Current Constraints

- `app.py` is 2,680 lines and combines CSS, HTML, data orchestration, filters, charts, map behavior, and six view implementations.
- Native `st.tabs` executes every tab body on each rerun.
- Dashboard data is loaded from four CSV files and six metrics files, while the same frames are filtered repeatedly for selected, map, and comparison scopes.
- The predictor uses chronological train, validation, and final-test partitions, but model selection currently uses one validation window even though rolling-origin results are already available.
- The final test must remain untouched by model selection, feature decisions, interval calibration, and tuning.

## Delivery Strategy

Work is split into three stages. Each stage receives focused tests, a full regression run, documentation updates, code review, and its own commit before the next stage starts.

1. Dashboard architecture
2. Data and rendering performance
3. Model selection and evaluation reliability

## Stage 1: Dashboard Architecture

Keep `app.py` as the composition root. It may initialize Streamlit, load configuration and theme state, build filters, render the shared header and KPI area, and dispatch the active view. It must not contain the detailed implementation of all six views.

Create a `src/dashboard/` package with the following boundaries:

- `context.py`: typed data contracts such as `DashboardData`, `FilterState`, `FilteredData`, and `DashboardMetrics`.
- `data_service.py`: data loading and construction of filtered scopes.
- `components.py`: shared table, metric, section header, Plotly theme, and safe HTML helpers.
- `pages/overview.py`: Taiwan map, station context, AQI and PM2.5 trends.
- `pages/comparison.py`: two-to-three station decision comparison.
- `pages/prediction.py`: prediction charts, intervals, errors, and backtest summaries.
- `pages/anomaly.py`: anomaly events, timeline, evidence, and station counts.
- `pages/quality.py`: data completeness and reliability views.
- `pages/metrics.py`: predictor and anomaly metric summaries.

Every page renderer receives explicit context arguments. Page modules must not read CSV, JSON, configuration, model artifacts, or Streamlit session state directly. The target size for `app.py` is approximately 500-800 lines, but clean ownership boundaries take priority over an arbitrary line count.

Existing imports used by tests or external callers remain available through compatibility re-exports during this stage. HTML values derived from data continue to be escaped before use with `unsafe_allow_html=True`.

## Stage 2: Data and Rendering Performance

Introduce file-version-aware caching for dashboard CSV and JSON inputs. A cache key contains the resolved path, file modification time, and file size. Updating a pipeline artifact therefore invalidates the relevant cache automatically.

Construct three filtered scopes once per rerun:

- `selected`: county, station, and date filters for detailed views.
- `regional`: county and date filters for the Taiwan map.
- `comparison`: date filter only for cross-region station comparison.

Page renderers consume these scopes and do not repeat the same filtering work.

Replace native `st.tabs` with a tab-like `st.segmented_control`. Only the selected page renderer executes. Preserve the six labels and current page order:

1. Overview
2. Region comparison
3. Prediction
4. Anomaly detection
5. Data quality
6. Model metrics

The control must remain keyboard accessible, have a minimum 44px touch target, use a two-row three-column layout at 390px, and maintain existing theme contrast requirements.

Performance verification is behavioral rather than tied to one machine. Tests must prove that unchanged files are not read again, changed files invalidate the cache, filter scopes are built once, and one page selection invokes only one renderer. A small benchmark command records cold load, warm load, and individual renderer timing for before-and-after comparison.

## Stage 3: Model Reliability

Use rolling-origin aggregate RMSE from data before the final test as the formal candidate-model selection basis. A single validation window may remain in the report but cannot be the sole selection criterion.

Retain Moving Average, Linear Regression, and Random Forest. Do not add another dependency or model family unless the existing candidates are shown to be insufficient in pre-test evaluation.

Add a station-hour historical baseline feature. For each row, it is calculated only from earlier observations for the same station and hour. If that history is insufficient, fall back to earlier observations for the station, then to earlier global observations. Current or future target values must never enter this feature.

The final test is evaluated once after model selection. It is not used for feature design, model choice, hyperparameter choice, or conformal calibration.

Extend predictor reporting with:

- Per-station MAE, RMSE, R2, and row count.
- Error by AQI category or configured AQI band.
- Absolute and percentage improvement over Moving Average.
- Worst-station summary with sample size.
- Per-station 80% and 95% interval coverage with sample size.
- Explicit selection basis, fold count, and pre-test evaluation period.

A candidate may be labeled best only when it improves pre-test rolling-origin RMSE over Moving Average. Otherwise, the simpler baseline remains the honest selected model.

## Error Handling

- Missing optional artifacts produce a clear empty state in the relevant page.
- Missing required columns raise a named data-contract error before rendering.
- Cache metadata failures fall back to an uncached safe read and report the affected artifact without exposing local paths in the UI.
- An unavailable optional model candidate is excluded and recorded in metrics; it does not silently change the selection rule.
- Insufficient historical rows for the new feature use the documented fallback chain. Rows that still cannot produce valid required features are excluded and counted.
- Existing model files remain restricted to the local `models/` directory and are never loaded from user-supplied paths.

## Testing and Verification

Each stage follows test-driven development and must keep the existing suite green.

Stage 1 tests:

- Page modules import independently.
- Renderers accept explicit contexts and handle empty inputs.
- `app.py` dispatches all six views without embedding their detailed implementations.
- Existing safe HTML and theme contracts remain intact.

Stage 2 tests:

- Cache hits avoid repeated physical reads.
- File version changes invalidate the cache.
- Each filter scope has the documented semantics.
- Selecting one view invokes only its renderer.
- Desktop and 390px controls have no overflow, overlap, raw JSON, or raw code.

Stage 3 tests:

- Future-row mutation cannot change current or earlier historical baseline features.
- Stations never contribute history to another station's baseline.
- Rolling-origin selection never reads final-test targets.
- Final reports include all group metrics and sample counts.
- Conformal calibration uses only pre-test residuals.

Full verification after every stage:

```text
python run_all.py --mode sample
python src/smoke_test.py
pytest -q
python -m pip check
python -m pip_audit --local
git diff --check
```

The final stage also receives a complete secret scan, generated-artifact tracking check, desktop browser review, 390px browser review, and browser console inspection.

## Non-Goals

- No framework rewrite, React frontend, database, authentication, deployment platform, or new external API.
- No visual redesign unrelated to the new tab-like lazy navigation.
- No new model family merely to increase project complexity.
- No final-test-driven tuning or claims that Sample Data metrics represent production performance.
- No GitHub push as part of local implementation unless explicitly requested later.

## Success Criteria

- The six user-facing views and current downloads remain functional.
- `app.py` becomes a readable composition root with independently testable pages.
- Only the active view renders on interaction.
- Dashboard files are cached with correct invalidation and filter work is not duplicated.
- Model selection is based on pre-test rolling-origin evidence.
- New historical features pass explicit no-leakage and station-isolation tests.
- Full pipeline, tests, dependency audit, security checks, and desktop/mobile visual checks pass.
