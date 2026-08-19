from __future__ import annotations

from datetime import date

from src.dashboard.filters import format_date_range, resolve_date_range


DATE_LIMITS = (date(2026, 8, 1), date(2026, 8, 30))


def test_all_data_preset_keeps_full_date_range() -> None:
    assert resolve_date_range(DATE_LIMITS, "全部資料") == DATE_LIMITS


def test_relative_preset_is_clamped_to_available_data() -> None:
    assert resolve_date_range(DATE_LIMITS, "最近 7 天") == (date(2026, 8, 24), date(2026, 8, 30))


def test_custom_range_is_reordered_and_clamped() -> None:
    assert resolve_date_range(DATE_LIMITS, "自訂日期", (date(2026, 8, 31), date(2026, 8, 5))) == (
        date(2026, 8, 5),
        date(2026, 8, 30),
    )


def test_date_range_format_is_explicit_for_the_dashboard() -> None:
    assert format_date_range(DATE_LIMITS) == "2026/08/01 - 2026/08/30"
    assert format_date_range(None) == "尚無日期"