"""Acceptance tests that check each analysis against the generator's ground truth."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analytics import attribution, forecast, propagation, whatif
from src.analytics.panel import build_panels
from src.generate_sample_data import SITES, TRANSPORT_LAG_HOURS, generate_sample_aqi
from src.preprocess import preprocess


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    directory = tmp_path_factory.mktemp("synthetic")
    sample = directory / "sample_aqi.csv"
    generate_sample_aqi(output_path=sample, metadata_path=directory / "meta.json")
    cleaned = preprocess(mode="sample", input_path=sample, source_metadata={"status": "success", "data_source": "Sample Data"})
    return {"panels": build_panels(cleaned), "truth": pd.read_csv(directory / "injected_events.csv"), "sample": sample}


def test_generator_is_byte_for_byte_reproducible(tmp_path: Path, synthetic: dict[str, object]) -> None:
    again = tmp_path / "again.csv"
    generate_sample_aqi(output_path=again, metadata_path=tmp_path / "meta.json")
    digest = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()  # noqa: E731
    assert digest(again) == digest(synthetic["sample"])
    assert digest(tmp_path / "injected_events.csv") == digest(Path(synthetic["sample"]).with_name("injected_events.csv"))


def test_detected_propagation_lags_match_the_injected_transport(synthetic: dict[str, object]) -> None:
    links, matrix = propagation.lead_lag_links(synthetic["panels"]["pm25"])
    west = set(TRANSPORT_LAG_HOURS)
    assert links, "the west-coast plume must be detected"
    for link in links:
        assert link.upstream in west and link.downstream in west
        truth = TRANSPORT_LAG_HOURS[link.downstream] - TRANSPORT_LAG_HOURS[link.upstream]
        assert abs(link.lag_hours - truth) <= 1, link
    detected = {(l.upstream, l.downstream) for l in links}
    for a in west:
        for b in west:
            if TRANSPORT_LAG_HOURS[b] - TRANSPORT_LAG_HOURS[a] >= 2:
                assert (a, b) in detected, (a, b)
    east = {s for s, *_ in SITES} - west
    for station in east:
        for other, cell in matrix[station].items():
            assert cell["r"] < propagation.MIN_CORRELATION, (station, other)


def test_nearest_upstream_follows_the_coast(synthetic: dict[str, object]) -> None:
    links, _ = propagation.lead_lag_links(synthetic["panels"]["pm25"])
    upstream = propagation.nearest_upstream(links)
    for downstream, link in upstream.items():
        assert TRANSPORT_LAG_HOURS[link.upstream] < TRANSPORT_LAG_HOURS[downstream]
    start, end = propagation.strongest_episode(synthetic["panels"]["pm25"], list(TRANSPORT_LAG_HOURS))
    assert start < end


def test_cross_correlation_peaks_at_the_true_lag_and_skips_sparse_pairs() -> None:
    rng = np.random.default_rng(3)
    base = rng.normal(size=500)
    shifted = np.concatenate([np.full(4, np.nan), base[:-4]])
    ccf = propagation.cross_correlation(base, shifted, max_lag=6)
    assert max(ccf, key=lambda k: ccf[k] if not np.isnan(ccf[k]) else -1) == 4
    sparse = propagation.cross_correlation(np.full(20, 1.0), np.full(20, 1.0), max_lag=2)
    assert all(np.isnan(v) for v in sparse.values())


def test_injected_events_are_recalled_and_explained(synthetic: dict[str, object]) -> None:
    events = attribution.detect_events(synthetic["panels"])
    assert attribution.recall(events, synthetic["truth"]) >= 0.8
    for event in events:
        drivers = event.drivers()
        magnitudes = [abs(d["z"]) for d in drivers]
        assert magnitudes == sorted(magnitudes, reverse=True)
        assert event.duration_hours >= 1
        assert event.event_id not in [s["event_id"] for s in event.similar]
        distances = [s["distance"] for s in event.similar]
        assert distances == sorted(distances)
    assert {e.kind for e in events} == {"local", "regional"}
    assert np.isnan(attribution.recall(events, synthetic["truth"].iloc[0:0]))


def test_robust_z_ignores_flat_series() -> None:
    index = pd.date_range("2026-01-01", periods=48, freq="h")
    z = attribution.robust_z(pd.DataFrame({"flat": np.ones(48)}, index=index))
    assert z["flat"].isna().all()


def test_forecast_intervals_are_ordered_calibrated_and_beat_persistence(synthetic: dict[str, object]) -> None:
    result = forecast.fit_forecaster(synthetic["panels"])
    assert [h.horizon for h in result.horizons] == list(forecast.HORIZONS)
    for horizon in result.horizons:
        assert horizon.half_width > 0
        assert horizon.calibration_size > 0
        assert np.isfinite(horizon.calibration_median_residual)
        assert np.isfinite(horizon.shifted_test_mae)
        assert 0.7 <= horizon.test_coverage <= 0.97, horizon.horizon
        assert horizon.test_mae < horizon.persistence_mae, horizon.horizon
        assert set(horizon.station_mae) == set(synthetic["panels"]["aqi"].columns)
    for station, rows in result.forecasts.items():
        assert len(rows) == 24, station
        for row in rows:
            assert 0 <= row["p10"] <= row["p50"] <= row["p90"]
    assert result.split["train_end"] < result.split["calibration_end"] < result.split["test_end"]


def test_conformal_half_width_is_the_finite_sample_quantile_of_absolute_residuals() -> None:
    # n = 5, level 0.8: rank ceil(6 × 0.8) = 5, the largest absolute residual.
    assert forecast.conformal_half_width(np.array([-4.0, 1.0, -2.0, 3.0, 5.0])) == 5.0
    # n = 9: rank ceil(10 × 0.8) = 8 of the sorted |residuals| 1…9.
    assert forecast.conformal_half_width(np.array([-9.0, 8.0, -7.0, 6.0, -5.0, 4.0, -3.0, 2.0, -1.0])) == 8.0
    # The sign of the errors is irrelevant: a biased window widens the band, it does not move it.
    residuals = np.linspace(-20.0, 2.0, 200)
    assert forecast.conformal_half_width(residuals) == forecast.conformal_half_width(-residuals)
    with pytest.raises(ValueError):
        forecast.conformal_half_width(np.array([]))
    with pytest.raises(ValueError):
        forecast.conformal_half_width(np.array([1.0, np.nan]))


def test_published_p50_is_the_unshifted_point_forecast_inside_a_symmetric_band(synthetic: dict[str, object]) -> None:
    panels = synthetic["panels"]
    result = forecast.fit_forecaster(panels)
    aqi = panels["aqi"]
    train_end, _ = forecast.split_times(aqi.index)
    climatology = forecast._climatology(aqi, train_end)
    for horizon in (result.horizons[0], result.horizons[11], result.horizons[23]):
        table = forecast.design_matrix(panels, climatology, horizon.horizon)
        latest = table[table["origin"] == aqi.index[-1]].set_index("station")
        for station, rows in result.forecasts.items():
            row = next(r for r in rows if r["h"] == horizon.horizon)
            point = float(horizon.model.predict(latest.loc[station, result.features].to_numpy(dtype=float)[None, :])[0])
            assert row["p50"] == round(max(point, 0.0), 1)
            assert row["p90"] == round(point + horizon.half_width, 1)
            assert row["p10"] == round(max(point - horizon.half_width, 0.0), 1)


def test_upstream_features_are_added_when_known(synthetic: dict[str, object]) -> None:
    links, _ = propagation.lead_lag_links(synthetic["panels"]["pm25"])
    upstream = {k: v.upstream for k, v in propagation.nearest_upstream(links).items()}
    result = forecast.fit_forecaster(synthetic["panels"], upstream=upstream)
    assert forecast.UPSTREAM_FEATURE in result.features
    downstream = sorted(upstream)
    short = [h for h in result.horizons if h.horizon <= 6]
    base = forecast.fit_forecaster(synthetic["panels"])
    improved = sum(
        np.mean([e.station_mae[s] for s in downstream]) < np.mean([b.station_mae[s] for s in downstream])
        for b, e in zip(base.horizons[:6], short)
    )
    assert improved >= 4  # upstream information helps most short horizons downstream


def test_whatif_payload_reproduces_the_model(synthetic: dict[str, object]) -> None:
    model, payload = whatif.fit_whatif(synthetic["panels"])
    assert len(payload["parity_cases"]) == 12
    for case in payload["parity_cases"]:
        assert whatif.predict_from_payload(payload, case["inputs"]) == pytest.approx(case["expected"], abs=1e-9)
        assert 0 <= case["inputs"]["hour"] <= 23
    assert payload["residual_p10"] < 0 < payload["residual_p90"]
    assert [i["key"] for i in payload["inputs"]] == [k for k, _, _ in whatif.INPUTS]
    aqi_coefficient = payload["coefficients"][payload["feature_order"].index("aqi_now")]
    assert aqi_coefficient > 0  # higher current AQI → higher next-hour AQI


def test_generator_rejects_invalid_ranges() -> None:
    with pytest.raises(ValueError):
        generate_sample_aqi(days=0)
