from __future__ import annotations

import pandas as pd
import pytest

from src.time_segments import hourly_segments


@pytest.mark.parametrize("dtype", ["object", "string[python]", "string[pyarrow]"])
def test_segments_are_portable_and_do_not_bridge_station_or_elapsed_gaps(dtype):
    frame = pd.DataFrame({
        "site_name": pd.Series(["A", "A", "A", "A", "A", "B", "B"], dtype=dtype),
        "datetime": pd.to_datetime([
            "2026-01-01 23:00", "2026-01-02 00:00", "2026-01-02 02:00",
            "2026-01-02 05:00", "2026-01-02 09:00", "2026-01-02 09:00",
            "2026-01-02 10:00",
        ]),
    }, index=None)
    assert hourly_segments(frame).tolist() == [1, 1, 2, 3, 4, 5, 5]
    assert str(hourly_segments(frame).dtype) == "int64"


@pytest.mark.parametrize("dtype", ["object", "string[python]", "string[pyarrow]"])
def test_missing_identity_timestamp_and_duplicate_hour_are_boundaries(dtype):
    frame = pd.DataFrame({
        "site_name": pd.Series(["A", None, "A", "A", "A", "A"], dtype=dtype),
        "datetime": pd.to_datetime([
            "2026-01-01 00:00", "2026-01-01 01:00", "2026-01-01 02:00",
            None, "2026-01-01 04:00", "2026-01-01 04:00",
        ]),
    })
    assert hourly_segments(frame).tolist() == [1, 2, 3, 4, 5, 6]


@pytest.mark.parametrize("dtype", ["object", "string[python]", "string[pyarrow]"])
def test_empty_single_row_and_nondefault_index(dtype):
    empty = pd.DataFrame({
        "site_name": pd.Series([], dtype=dtype),
        "datetime": pd.Series([], dtype="datetime64[ns]"),
    })
    assert hourly_segments(empty).empty
    one = pd.DataFrame({
        "site_name": pd.Series(["A"], index=[17], dtype=dtype),
        "datetime": pd.Series(pd.to_datetime(["2026-01-01"]), index=[17]),
    })
    pd.testing.assert_series_equal(hourly_segments(one), pd.Series([1], index=[17]), check_names=False)
