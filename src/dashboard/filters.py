from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any


DATE_RANGE_OPTIONS = ("全部資料", "最近 3 天", "最近 7 天", "自訂日期")
DATE_RANGE_DAYS = {
    "最近 3 天": 3,
    "最近 7 天": 7,
}


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def normalize_date_range(value: Any) -> tuple[date, date] | None:
    if isinstance(value, (tuple, list)) and len(value) == 2:
        start, end = _as_date(value[0]), _as_date(value[1])
        if start is not None and end is not None:
            return (start, end) if start <= end else (end, start)
    single = _as_date(value)
    return (single, single) if single is not None else None


def resolve_date_range(
    date_limits: tuple[Any, Any] | None,
    selection: str,
    custom_range: Any = None,
) -> tuple[date, date] | None:
    """Resolve a user-facing preset into an inclusive date range."""
    limits = normalize_date_range(date_limits)
    if limits is None:
        return None
    minimum, maximum = limits
    if selection == "自訂日期":
        custom = normalize_date_range(custom_range)
        if custom is None:
            return limits
        start = max(minimum, custom[0])
        end = min(maximum, custom[1])
        return (start, end) if start <= end else limits
    days = DATE_RANGE_DAYS.get(selection)
    if days is None:
        return limits
    return (max(minimum, maximum - timedelta(days=days - 1)), maximum)


def format_date_range(date_range: tuple[Any, Any] | None) -> str:
    normalized = normalize_date_range(date_range)
    if normalized is None:
        return "尚無日期"
    start, end = normalized
    return f"{start:%Y/%m/%d} - {end:%Y/%m/%d}"
