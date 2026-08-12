# Station Comparison Decision View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tested, responsive station comparison workflow for two or three AQI stations.

**Architecture:** A focused `station_comparison` module builds the comparison contract and recommendation independently of Streamlit. `app.py` renders that contract in a new tab using existing theme, chart and table helpers.

**Tech Stack:** Python 3.12, pandas, Streamlit, Plotly, pytest

## Global Constraints

- Compare two or three stations, with a hard maximum of three.
- Treat observations more than two hours behind the newest selected station as stale.
- Prefer next-hour forecast for recommendation and fall back to current AQI.
- Never present the result as an official alert, medical recommendation, route recommendation, or guaranteed outcome.
- Keep Sample Data visibly labeled as simulated data.
- Export only user-facing fields with UTF-8 BOM.

---

### Task 1: Comparison Data Contract

**Files:**
- Create: `src/station_comparison.py`
- Create: `tests/test_station_comparison.py`

**Interfaces:**
- Produces: `build_station_comparison(...) -> pd.DataFrame`
- Produces: `choose_recommended_station(comparison) -> dict[str, object]`
- Produces: `export_comparison_csv(comparison) -> bytes`

- [ ] Write tests for latest-row isolation, exact forecast/anomaly matching, stale exclusion, fallback, empty data, and safe export.
- [ ] Run `python -m pytest -q tests/test_station_comparison.py` and confirm collection fails because the module does not exist.
- [ ] Implement the minimal comparison module.
- [ ] Run `python -m pytest -q tests/test_station_comparison.py` and confirm all tests pass.
- [ ] Refactor names and column ordering while keeping the focused tests green.

### Task 2: Dashboard Comparison Tab

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app_import.py`

**Interfaces:**
- Consumes: the three public functions from `src.station_comparison`
- Produces: `comparison_cards_html(comparison) -> str`

- [ ] Add failing source and HTML tests for the new tab, selector, recommendation copy, cards and mobile CSS.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Add comparison display labels, high-contrast CSS and escaped card HTML.
- [ ] Add the sixth tab, two-to-three station selector, recommendation band, grouped chart, 24-hour trend, table and CSV download.
- [ ] Run app import and comparison tests until green.

### Task 3: Documentation and Product Positioning

**Files:**
- Modify: `README.md`

- [ ] Document the comparison workflow, recommendation basis, stale-data rule and limitations.
- [ ] Add the feature to the Dashboard and interview-demo sections.
- [ ] Scan README for contradictory claims or wording that implies official guidance.

### Task 4: Full Verification

**Files:**
- No production file changes unless verification exposes a defect.

- [ ] Run `python run_all.py --mode sample`.
- [ ] Run `python src/smoke_test.py`.
- [ ] Run `python -m pytest -q`.
- [ ] Run `python -m pip check` and `python -m pip_audit --local`.
- [ ] Run `git diff --check` and the secret-assignment scan.
- [ ] Verify all six tabs, comparison selection, desktop layout, 390px mobile layout, console logs, overflow and raw-code exposure in a real browser.
- [ ] Re-run focused tests after any visual defect fix.
