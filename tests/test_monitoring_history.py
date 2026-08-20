from __future__ import annotations

import json

from src.monitoring_history import build_monitoring_snapshot, update_monitoring_history


def _monitoring_report(
    *,
    status: str = "stable",
    current_mae: float = 5.0,
    retraining_recommended: bool = False,
) -> dict[str, object]:
    return {
        "monitoring_version": "1.0",
        "status": status,
        "prediction": {
            "reference_mae": 4.0,
            "current_mae": current_mae,
            "mae_change_pct": 25.0,
        },
        "coverage": {
            "80": {"current": 0.81},
            "95": {"current": 0.96},
        },
        "signals": [
            {"column": "aqi", "standardized_mean_shift": 0.3},
            {"column": "pm25", "standardized_mean_shift": 0.2},
        ],
        "retraining": {
            "recommended": retraining_recommended,
            "reasons": ["Current MAE increased beyond the warning threshold."]
            if retraining_recommended
            else [],
        },
    }


def test_snapshot_flattens_monitoring_evidence_and_assigns_action() -> None:
    snapshot = build_monitoring_snapshot(
        _monitoring_report(status="warning"),
        data_end="2026-08-20T12:00:00",
        data_source="Sample Data",
        model_name="random_forest",
        recorded_at_utc="2026-08-20T04:30:00Z",
    )

    assert snapshot["snapshot_version"] == "1.0"
    assert snapshot["snapshot_id"]
    assert snapshot["recorded_at_utc"] == "2026-08-20T04:30:00Z"
    assert snapshot["status"] == "warning"
    assert snapshot["action"] == "investigate"
    assert snapshot["reference_mae"] == 4.0
    assert snapshot["current_mae"] == 5.0
    assert snapshot["coverage_80"] == 0.81
    assert snapshot["coverage_95"] == 0.96
    assert snapshot["aqi_shift"] == 0.3
    assert snapshot["pm25_shift"] == 0.2


def test_snapshot_uses_retraining_and_insufficient_data_actions() -> None:
    retraining = build_monitoring_snapshot(
        _monitoring_report(status="critical", retraining_recommended=True),
        data_end="2026-08-20T12:00:00",
        data_source="API Data",
        model_name="random_forest",
    )
    insufficient = build_monitoring_snapshot(
        _monitoring_report(status="insufficient_data"),
        data_end="2026-08-20T12:00:00",
        data_source="Sample Data",
        model_name="random_forest",
    )

    assert retraining["action"] == "review_retraining"
    assert retraining["retraining_recommended"] is True
    assert insufficient["action"] == "collect_more_data"


def test_history_deduplicates_same_data_and_model_run(tmp_path) -> None:
    path = tmp_path / "monitoring_history.json"
    first = build_monitoring_snapshot(
        _monitoring_report(),
        data_end="2026-08-20T12:00:00",
        data_source="Sample Data",
        model_name="random_forest",
        recorded_at_utc="2026-08-20T04:30:00Z",
    )
    rerun = {**first, "recorded_at_utc": "2026-08-20T04:35:00Z", "current_mae": 4.8}

    update_monitoring_history(path, first, max_entries=10)
    history = update_monitoring_history(path, rerun, max_entries=10)

    assert len(history["entries"]) == 1
    assert history["entries"][0]["current_mae"] == 4.8
    assert history["entries"][0]["recorded_at_utc"] == "2026-08-20T04:35:00Z"


def test_monitoring_policy_changes_create_a_distinct_snapshot() -> None:
    default_policy_report = _monitoring_report()
    default_policy_report["policy"] = {
        "reference_days": 14,
        "current_days": 7,
        "thresholds": {"mae_increase_warning_pct": 25.0},
    }
    changed_policy_report = _monitoring_report()
    changed_policy_report["policy"] = {
        "reference_days": 30,
        "current_days": 7,
        "thresholds": {"mae_increase_warning_pct": 25.0},
    }

    first = build_monitoring_snapshot(
        default_policy_report,
        data_end="2026-08-20T12:00:00",
        data_source="Sample Data",
        model_name="random_forest",
    )
    changed = build_monitoring_snapshot(
        changed_policy_report,
        data_end="2026-08-20T12:00:00",
        data_source="Sample Data",
        model_name="random_forest",
    )

    assert first["policy_hash"] != changed["policy_hash"]
    assert first["snapshot_id"] != changed["snapshot_id"]


def test_history_keeps_latest_entries_in_chronological_order(tmp_path) -> None:
    path = tmp_path / "monitoring_history.json"
    for day in (20, 18, 19):
        snapshot = build_monitoring_snapshot(
            _monitoring_report(current_mae=float(day)),
            data_end=f"2026-08-{day:02d}T12:00:00",
            data_source="Sample Data",
            model_name="random_forest",
            recorded_at_utc=f"2026-08-{day:02d}T04:30:00Z",
        )
        history = update_monitoring_history(path, snapshot, max_entries=2)

    assert [entry["current_mae"] for entry in history["entries"]] == [19.0, 20.0]
    assert history["entry_count"] == 2


def test_history_recovers_from_malformed_existing_file(tmp_path) -> None:
    path = tmp_path / "monitoring_history.json"
    path.write_text("{not-valid-json", encoding="utf-8")
    snapshot = build_monitoring_snapshot(
        _monitoring_report(),
        data_end="2026-08-20T12:00:00",
        data_source="Sample Data",
        model_name="random_forest",
        recorded_at_utc="2026-08-20T04:30:00Z",
    )

    history = update_monitoring_history(path, snapshot, max_entries=10)
    persisted = json.loads(path.read_text(encoding="utf-8"))

    assert history["entry_count"] == 1
    assert persisted == history
    assert persisted["history_version"] == "1.0"
