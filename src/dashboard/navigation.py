from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


VIEW_LABELS = ("總覽", "地區比較", "預測", "異常偵測", "資料品質", "模型指標")


def render_active_view(
    selected_view: str,
    context: Any,
    renderers: Mapping[str, Callable[[Any], None]],
) -> None:
    if selected_view not in VIEW_LABELS or selected_view not in renderers:
        raise ValueError(f"Unknown dashboard view: {selected_view}")
    renderers[selected_view](context)
