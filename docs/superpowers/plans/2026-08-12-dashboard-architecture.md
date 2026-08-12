# Dashboard Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Turn `app.py` into a composition root with explicit page contexts and six independently testable page renderers.

**Architecture:** A new `src.dashboard` package owns typed context contracts, shared components, styles, maps, and page renderers. `app.py` keeps startup, sidebar state, shared header/KPI rendering, and compatibility re-exports.

**Tech Stack:** Python 3.12, dataclasses, pandas, Streamlit, Plotly, pytest

## Global Constraints

- Preserve all six user-facing views, downloads, Chinese copy, theme behavior, and security disclaimers.
- Page modules must not read files, configuration, model artifacts, or session state.
- Data-derived values passed to unsafe HTML must be escaped.
- Work on the current non-`main` feature branch and keep generated artifacts untracked.
- Follow red-green-refactor for every new public interface.

---

### Task 1: Typed Dashboard Contexts

**Files:**
- Create: `src/dashboard/__init__.py`
- Create: `src/dashboard/context.py`
- Create: `tests/test_dashboard_context.py`

**Interfaces:**
- Produces: `DashboardData`, `FilteredData`, `DashboardMetrics`, `FilterState`, `PageContext`, `DataContractError`
- Consumes: pandas DataFrames and existing metric dictionaries

- [x] **Step 1: Write failing context tests**

```python
def test_dashboard_data_requires_named_frames():
    data = DashboardData.empty()
    assert data.features.empty
    assert data.predictions.empty
    assert data.anomalies.empty
    assert data.events.empty

def test_page_context_validates_required_selected_columns():
    context = make_context(features=pd.DataFrame({"aqi": [1]}))
    with pytest.raises(DataContractError, match="datetime"):
        context.validate_selected_features({"datetime", "aqi"})
```

- [x] **Step 2: Verify RED**

Run: `python -m pytest -q tests/test_dashboard_context.py`
Expected: collection fails because `src.dashboard.context` does not exist.

- [x] **Step 3: Implement immutable contracts**

```python
@dataclass(frozen=True)
class DashboardData:
    features: pd.DataFrame
    predictions: pd.DataFrame
    anomalies: pd.DataFrame
    events: pd.DataFrame

    @classmethod
    def empty(cls) -> "DashboardData":
        return cls(*(pd.DataFrame() for _ in range(4)))

@dataclass(frozen=True)
class FilteredData:
    selected: DashboardData
    regional: DashboardData
    comparison: DashboardData

@dataclass(frozen=True)
class DashboardMetrics:
    predictor: dict[str, Any]
    anomaly: dict[str, Any]
    backtest: dict[str, Any]
    confidence: dict[str, Any]
    data_health: dict[str, Any]
    evaluation: dict[str, Any]

@dataclass(frozen=True)
class FilterState:
    county: str | None
    site_name: str | None
    site_display: str
    start_date: Any | None
    end_date: Any | None

class DataContractError(ValueError):
    pass
```

- [x] **Step 4: Verify GREEN**

Run: `python -m pytest -q tests/test_dashboard_context.py`
Expected: all context tests pass.

- [x] **Step 5: Commit**

```bash
git add src/dashboard tests/test_dashboard_context.py
git commit -m "refactor: add typed dashboard contexts"
```

### Task 2: Shared Components, Styles, and Map Module

**Files:**
- Create: `src/dashboard/components.py`
- Create: `src/dashboard/styles.py`
- Create: `src/dashboard/maps.py`
- Modify: `app.py`
- Create: `tests/test_dashboard_components.py`
- Modify: `tests/test_app_import.py`

**Interfaces:**
- Produces: `inject_global_css`, `metric_card`, `signal_deck`, `section_header`, `render_table`, `apply_plotly_theme`, `comparison_cards_html`, `render_station_map`
- Consumes: explicit Streamlit object where rendering is required, theme dictionaries, and DataFrames

- [x] **Step 1: Add failing import and escaping tests**

```python
def test_comparison_cards_escape_station_labels():
    frame = pd.DataFrame({
        "site_name_display": ["<script>x</script>"],
        "county_display": ["臺北市"],
        "observed_at": [pd.Timestamp("2026-08-12 10:00")],
        "freshness_state": ["可比較"],
        "current_aqi": [65.0],
        "aqi_category": ["普通"],
        "pm25": [22.0],
        "predicted_next_hour_aqi": [62.0],
        "lower_80_aqi": [56.0],
        "upper_80_aqi": [68.0],
        "is_anomaly": [False],
    })
    html = comparison_cards_html(frame)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html

def test_app_reexports_component_helpers():
    assert app.render_table is dashboard_components.render_table
```

- [x] **Step 2: Verify RED**

Run: `python -m pytest -q tests/test_dashboard_components.py tests/test_app_import.py`
Expected: imports fail because the new modules do not exist.

- [x] **Step 3: Extract pure formatting and HTML helpers first**

```python
def comparison_cards_html(comparison: pd.DataFrame) -> str:
    cards = [_comparison_card_html(row) for _, row in comparison.iterrows()]
    return f'<section class="comparison-grid" aria-label="測站比較卡片">{"".join(cards)}</section>'

def render_table(st_api: Any, df: pd.DataFrame, label: str = "資料表", table_class: str = "dashboard-table") -> None:
    html = df.to_html(index=False, escape=True, classes=table_class, border=0)
    st_api.markdown(
        f'<div class="table-shell" role="region" aria-label="{escape(label)}" tabindex="0">{html}</div>',
        unsafe_allow_html=True,
    )
```

- [x] **Step 4: Move CSS and station map functions without behavior changes**

`styles.py` owns `inject_global_css`. `maps.py` owns `_station_map_data`, `_build_station_map`, and `render_station_map`. Pass `st_api`, `theme`, and selected station explicitly instead of reading globals.

- [x] **Step 5: Re-export compatibility names from `app.py` and verify GREEN**

Run: `python -m pytest -q tests/test_dashboard_components.py tests/test_app_import.py`
Expected: component and legacy import tests pass.

- [x] **Step 6: Commit**

```bash
git add app.py src/dashboard tests/test_dashboard_components.py tests/test_app_import.py
git commit -m "refactor: extract dashboard components and styles"
```

### Task 3: Overview and Comparison Renderers

**Files:**
- Create: `src/dashboard/pages/__init__.py`
- Create: `src/dashboard/pages/overview.py`
- Create: `src/dashboard/pages/comparison.py`
- Modify: `app.py`
- Create: `tests/test_dashboard_pages.py`

**Interfaces:**
- Produces: `render_overview(st_api, context) -> None`, `render_comparison(st_api, context) -> None`
- Consumes: `PageContext`, shared components, map module, risk brief, and station comparison functions

- [x] **Step 1: Write failing renderer tests**

```python
def test_overview_empty_state_is_rendered(fake_streamlit, empty_context):
    render_overview(fake_streamlit, empty_context)
    assert fake_streamlit.info_messages

def test_comparison_does_not_read_files(monkeypatch, fake_streamlit, context):
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: pytest.fail("page read a file"))
    render_comparison(fake_streamlit, context)
```

- [x] **Step 2: Verify RED**

Run: `python -m pytest -q tests/test_dashboard_pages.py -k 'overview or comparison'`
Expected: page module imports fail.

- [x] **Step 3: Implement explicit renderers**

```python
def render_overview(st_api: Any, context: PageContext) -> None:
    features = context.data.selected.features
    if features.empty:
        st_api.info("目前篩選條件下沒有 AQI 資料。")
        return
    _render_map_and_risk(st_api, context)
    _render_trends(st_api, context)

def render_comparison(st_api: Any, context: PageContext) -> None:
    features = context.data.comparison.features
    if features.empty:
        st_api.info("目前日期範圍沒有可比較資料。")
        return
    _render_station_selector_and_comparison(st_api, context)
```

- [x] **Step 4: Replace the corresponding bodies in `app.py` with calls**

```python
with overview_tab:
    render_overview(st, page_context)
with comparison_tab:
    render_comparison(st, page_context)
```

- [x] **Step 5: Verify GREEN and regression tests**

Run: `python -m pytest -q tests/test_dashboard_pages.py tests/test_app_import.py tests/test_station_comparison.py tests/test_risk_brief.py`
Expected: all tests pass.

- [x] **Step 6: Commit**

```bash
git add app.py src/dashboard/pages tests/test_dashboard_pages.py
git commit -m "refactor: extract overview and comparison pages"
```

### Task 4: Prediction and Anomaly Renderers

**Files:**
- Create: `src/dashboard/pages/prediction.py`
- Create: `src/dashboard/pages/anomaly.py`
- Modify: `app.py`
- Modify: `tests/test_dashboard_pages.py`

**Interfaces:**
- Produces: `render_prediction(st_api, context) -> None`, `render_anomaly(st_api, context) -> None`
- Consumes: selected prediction/anomaly/event frames and `DashboardMetrics`

- [x] **Step 1: Add failing empty-state and no-file-read tests**
- [x] **Step 2: Verify RED with `python -m pytest -q tests/test_dashboard_pages.py -k 'prediction or anomaly'`**
- [x] **Step 3: Extract prediction rendering behind this interface**

```python
def render_prediction(st_api: Any, context: PageContext) -> None:
    predictions = context.data.selected.predictions
    if predictions.empty:
        st_api.info("找不到預測結果，請先執行完整 sample mode 流程。")
        return
    render_prediction_chart(st_api, context)
    render_confidence(st_api, context)
    render_error_and_model_tables(st_api, context)
```

- [x] **Step 4: Extract anomaly rendering behind this interface**

```python
def render_anomaly(st_api: Any, context: PageContext) -> None:
    anomalies = context.data.selected.anomalies
    render_event_summary(st_api, context.data.selected.events)
    if anomalies.empty:
        st_api.info("找不到異常偵測結果，請先執行完整 sample mode 流程。")
        return
    render_anomaly_timeline_and_cases(st_api, context)
```

- [x] **Step 5: Replace app bodies, run focused and full tests, then commit**

Run: `python -m pytest -q tests/test_dashboard_pages.py tests/test_app_import.py tests/test_forecast_confidence.py tests/test_anomaly_events.py`
Expected: all pass.

```bash
git add app.py src/dashboard/pages tests/test_dashboard_pages.py
git commit -m "refactor: extract prediction and anomaly pages"
```

### Task 5: Quality and Metrics Renderers

**Files:**
- Create: `src/dashboard/pages/quality.py`
- Create: `src/dashboard/pages/metrics.py`
- Modify: `app.py`
- Modify: `tests/test_dashboard_pages.py`

**Interfaces:**
- Produces: `render_quality(st_api, context) -> None`, `render_metrics(st_api, context) -> None`

- [x] **Step 1: Add failing renderer tests for empty metrics and no raw JSON**
- [x] **Step 2: Verify RED with `python -m pytest -q tests/test_dashboard_pages.py -k 'quality or metrics'`**
- [x] **Step 3: Extract both renderers with explicit context arguments**
- [x] **Step 4: Replace app bodies with renderer calls**
- [x] **Step 5: Verify focused tests and full suite**

Run: `python -m pytest -q tests/test_dashboard_pages.py tests/test_app_import.py tests/test_data_health.py tests/test_evaluate.py`
Expected: all pass.

- [x] **Step 6: Commit**

```bash
git add app.py src/dashboard/pages tests/test_dashboard_pages.py
git commit -m "refactor: extract quality and metrics pages"
```

### Task 6: Composition Root and Architecture Verification

**Files:**
- Modify: `app.py`
- Modify: `README.md`
- Modify: `tests/test_app_import.py`
- Create: `tests/test_dashboard_architecture.py`

**Interfaces:**
- Produces: `build_page_context(filtered: FilteredData, metrics: DashboardMetrics, filters: FilterState, theme: dict[str, str], source_code: str, data_source: str) -> PageContext`, page dispatch calls, compatibility re-exports

- [x] **Step 1: Write failing architecture tests**

```python
def test_app_is_a_composition_root():
    source = Path("app.py").read_text(encoding="utf-8")
    assert source.count("\n") < 900
    for renderer in REQUIRED_RENDERERS:
        assert renderer in source

def test_page_modules_do_not_read_artifacts():
    for path in Path("src/dashboard/pages").glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "read_csv(" not in source
        assert "load_config(" not in source
        assert "load_model(" not in source
```

- [x] **Step 2: Verify RED**

Run: `python -m pytest -q tests/test_dashboard_architecture.py`
Expected: app line-count assertion fails until all duplicated blocks are removed.

- [x] **Step 3: Remove dead duplicates and complete compatibility re-exports**
- [x] **Step 4: Update README architecture section**
- [x] **Step 5: Run Stage 1 verification**

Run:

```text
python -m py_compile app.py src/dashboard/*.py src/dashboard/pages/*.py
python -m pytest -q
python src/smoke_test.py
git diff --check
```

Expected: all tests and checks pass; app contains fewer than 900 lines.

- [x] **Step 6: Commit**

```bash
git add app.py src/dashboard tests README.md
git commit -m "refactor: complete modular dashboard architecture"
```
