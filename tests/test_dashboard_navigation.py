from __future__ import annotations

import pytest

from src.dashboard.navigation import VIEW_LABELS, render_active_view


def test_view_labels_are_stable_traditional_chinese() -> None:
    assert VIEW_LABELS == (
        "總覽",
        "地區比較",
        "預測",
        "異常偵測",
        "資料品質",
        "模型指標",
    )

def test_only_selected_view_renderer_runs() -> None:
    calls: list[str] = []
    renderers = {label: (lambda _context, label=label: calls.append(label)) for label in VIEW_LABELS}

    render_active_view("預測", object(), renderers)

    assert calls == ["預測"]


def test_unknown_view_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown dashboard view"):
        render_active_view("不存在", object(), {})
