from __future__ import annotations

import importlib

from src.dashboard.styles import inject_global_css as inject_dashboard_css


class _FakeStreamlit:
    def __init__(self) -> None:
        self.rendered = ""

    def markdown(self, value: str, unsafe_allow_html: bool = False) -> None:
        assert unsafe_allow_html is True
        self.rendered = value


def test_dashboard_styles_render_high_contrast_responsive_css() -> None:
    app = importlib.import_module("app")
    fake = _FakeStreamlit()

    inject_dashboard_css(fake, app.THEME)

    assert ".signal-card" in fake.rendered
    assert ".comparison-card" in fake.rendered
    assert "var(--text)" in fake.rendered
    assert '[data-testid="stButtonGroup"]' in fake.rendered
    assert "min-height: 44px" in fake.rendered
    assert "width: 100% !important" in fake.rendered
    assert "repeat(3, minmax(0, 1fr))" in fake.rendered
    assert "@media (max-width: 640px)" in fake.rendered
    assert "button:focus-visible" in fake.rendered
    assert "outline: 3px solid var(--accent)" in fake.rendered
    assert "button:disabled" in fake.rendered
    assert "cursor: not-allowed" in fake.rendered
    assert "button:not(:disabled)" in fake.rendered
    assert '[data-testid="stExpandSidebarButton"]' in fake.rendered
    assert "min-width: 44px !important" in fake.rendered
    assert "cursor: pointer" in fake.rendered


def test_app_css_wrapper_uses_the_current_streamlit_binding(monkeypatch) -> None:
    app = importlib.import_module("app")
    fake = _FakeStreamlit()
    monkeypatch.setattr(app, "st", fake)

    app.inject_global_css(app.THEME)

    assert ".signal-card" in fake.rendered
