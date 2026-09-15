from __future__ import annotations

import importlib

from src.dashboard.styles import inject_global_css


class _FakeStreamlit:
    def __init__(self) -> None:
        self.rendered = ""

    def markdown(self, value: str, unsafe_allow_html: bool = False) -> None:
        assert unsafe_allow_html is True
        self.rendered = value


def test_ui_pro_max_tokens_cover_readability_and_reflow() -> None:
    app = importlib.import_module("app")
    fake = _FakeStreamlit()
    inject_global_css(fake, app.get_theme("paper_blue"))
    css = fake.rendered
    for token in (
        '--ui-font:',
        '--ui-data-font:',
        'box-sizing: border-box',
        'font-size: clamp(',
        'min-width: 0',
        'min-height: 44px',
        'overflow-x: auto',
        'outline: 3px solid var(--accent)',
        'prefers-reduced-motion: reduce',
    ):
        assert token in css


def test_light_theme_uses_the_same_css_contract() -> None:
    app = importlib.import_module("app")
    fake = _FakeStreamlit()
    inject_global_css(fake, app.get_theme("paper_blue"))
    assert 'color-scheme: light' in fake.rendered
    assert '--ui-content-gutter:' in fake.rendered
