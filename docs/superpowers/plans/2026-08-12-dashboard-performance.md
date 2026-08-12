# Dashboard Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Avoid repeated artifact reads, repeated filter work, and eager rendering of all six views.

**Architecture:** File signatures drive cached data reads, `build_filtered_data` creates three documented scopes once, and a segmented view selector dispatches exactly one page renderer.

**Tech Stack:** Python 3.12, pathlib, pandas, Streamlit cache, pytest, time.perf_counter

## Global Constraints

- Cache invalidation must use resolved path, modification time, and file size.
- Missing files return documented empty artifacts; malformed required data raises `DataContractError`.
- Preserve six view labels and order.
- Mobile selector uses two rows of three controls at 390px with 44px touch targets.
- Benchmarks record measurements but do not enforce machine-specific milliseconds.

---

### Task 1: Versioned Artifact Cache

**Files:**
- Modify: `src/dashboard/data_service.py`
- Create: `tests/test_dashboard_cache.py`

**Interfaces:**
- Produces: `file_signature(path) -> FileSignature | None`, `read_csv_versioned(path, parse_dates)`, `read_json_versioned(path)`

- [x] Write tests proving a second unchanged read does not call pandas again and a changed size or mtime does.
- [x] Run `python -m pytest -q tests/test_dashboard_cache.py` and confirm RED.
- [x] Implement `FileSignature(path: str, modified_ns: int, size: int)` and cached readers whose signature is an explicit argument.
- [x] Run focused tests and confirm GREEN.
- [x] Commit with `git commit -m "perf: cache dashboard artifacts by file version"`.

### Task 2: Three Filter Scopes

**Files:**
- Modify: `src/dashboard/data_service.py`
- Create: `tests/test_dashboard_scopes.py`
- Modify: `app.py`

**Interfaces:**
- Produces: `build_filtered_data(data: DashboardData, filters: FilterState) -> FilteredData`

- [x] Write failing tests for selected, regional, and comparison semantics.
- [x] Confirm RED.
- [x] Implement each scope once with a private `_filter_frame` helper.
- [x] Replace repeated app filtering with one `build_filtered_data` call.
- [x] Confirm focused and full tests pass.
- [x] Commit with `git commit -m "perf: build dashboard filter scopes once"`.

### Task 3: Lazy View Dispatch

**Files:**
- Create: `src/dashboard/navigation.py`
- Create: `tests/test_dashboard_navigation.py`
- Modify: `app.py`
- Modify: `src/dashboard/styles.py`

**Interfaces:**
- Produces: `VIEW_LABELS`, `render_active_view(st_api, selected_view, context, renderers) -> None`

- [x] Write a failing test where six spy renderers are registered and only the selected spy may run.
- [x] Confirm RED.
- [x] Implement strict label validation and one-renderer dispatch.
- [x] Replace `st.tabs` with `st.segmented_control("Dashboard view", options=VIEW_LABELS, default=VIEW_LABELS[0], label_visibility="collapsed", key="dashboard_view")` and call `render_active_view`.
- [x] Add responsive selector CSS for 44px controls and 3x2 mobile layout.
- [x] Run navigation, app, and full tests.
- [x] Commit with `git commit -m "perf: lazily render the active dashboard view"`.

### Task 4: Reproducible Benchmark and Verification

**Files:**
- Create: `src/benchmark_dashboard.py`
- Create: `tests/test_dashboard_benchmark.py`
- Modify: `README.md`

**Interfaces:**
- Produces: `benchmark_dashboard(config=None) -> dict[str, float | int]`

- [x] Write a failing test requiring `cold_load_ms`, `warm_load_ms`, `feature_rows`, and `scope_build_ms`.
- [x] Implement the benchmark with `perf_counter`, two loads, and one scope build.
- [x] Assert only non-negative values and warm-load reuse behavior, not a fixed speed ratio.
- [x] Document `python src/benchmark_dashboard.py`.
- [x] Run pipeline, smoke, full pytest, diff check, desktop and 390px selector verification.
- [x] Commit with `git commit -m "perf: add dashboard performance benchmark"`.
