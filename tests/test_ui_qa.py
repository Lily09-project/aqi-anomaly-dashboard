from __future__ import annotations

import json
from pathlib import Path

from scripts.ui_qa import (
    focus_issues,
    capture_scroll_evidence,
    SCROLL_EVIDENCE_MAX_SEGMENTS,
    CORE_VIEWPORTS,
    EXTENDED_VIEWPORTS,
    MIN_INTERACTIVE_TARGET_PX,
    STREAMLIT_EXCEPTION_SELECTOR,
    TEXT_SCALE_CSS,
    VIEW_CONTRACTS,
    VIEWPORTS,
    layout_issues,
    viewport_matrix,
    write_failure_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


def test_ui_qa_covers_every_public_view() -> None:
    assert set(VIEW_CONTRACTS) == {
        "總覽",
        "地區比較",
        "預測",
        "異常偵測",
        "資料品質",
        "模型指標",
    }


def test_ui_qa_covers_desktop_small_phone_and_landscape() -> None:
    viewports = {name: (width, height) for name, width, height in VIEWPORTS}
    assert viewports["desktop"] == (1440, 1000)
    assert viewports["small-mobile"] == (375, 812)
    assert viewports["tablet"] == (768, 1024)
    assert viewports["landscape"][0] > viewports["landscape"][1]
    assert viewports["wide-tablet"] == (1024, 768)
    assert viewport_matrix() == CORE_VIEWPORTS
    assert viewport_matrix(extended=True) == CORE_VIEWPORTS + EXTENDED_VIEWPORTS
    assert STREAMLIT_EXCEPTION_SELECTOR == '[data-testid="stException"]'
    assert "200%" in TEXT_SCALE_CSS


def test_layout_issues_is_fail_closed_for_browser_contract() -> None:
    assert callable(layout_issues)
    assert callable(focus_issues)
    assert MIN_INTERACTIVE_TARGET_PX == 44


def test_user_facing_streamlit_buttons_have_a_touch_target_floor() -> None:
    source = Path("src/dashboard/styles.py").read_text(encoding="utf-8")

    assert 'button[data-testid^="stBaseButton-"]' in source
    assert "min-height: 44px !important;" in source


def test_browser_qa_is_wired_into_ci_and_kept_out_of_release_artifacts() -> None:
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-e2e.txt").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "python scripts/ui_qa.py --url http://127.0.0.1:8851" in workflow
    assert (
        "python scripts/ui_qa.py --url http://127.0.0.1:8851 --extended --text-scale"
        in workflow
    )
    assert "python -m playwright install --with-deps chromium" in workflow
    assert 'PIP_DEFAULT_TIMEOUT: "60"' in workflow
    assert 'PIP_RETRIES: "10"' in workflow
    assert "playwright==1.58.0" in requirements
    assert "docs/screenshots/ui-qa/" in gitignore


def test_focus_audit_uses_real_keyboard_tab_navigation() -> None:
    source = Path("scripts/ui_qa.py").read_text(encoding="utf-8")

    assert 'page.keyboard.press("Tab")' in source
    assert "keyboard focus did not reach the skip link" in source
    assert ".focus({preventScroll: true})" not in source

    app_source = Path("app.py").read_text(encoding="utf-8")
    assert '<a class="skip-link" href="#dashboard-main" tabindex="0">' in app_source


def test_focus_audit_validates_radio_proxy_and_mobile_controls() -> None:
    source = Path("scripts/ui_qa.py").read_text(encoding="utf-8")
    start = source.index("def focus_issues(page)")
    focus_source = source[start:source.index(chr(10) + "def ", start + 1)]

    assert 'page.keyboard.press("Tab")' in focus_source
    assert "page.wait_for_function(" in focus_source
    assert "DOMMatrixReadOnly" in focus_source
    assert "document.body.setAttribute('tabindex', '-1')" in focus_source
    assert "page.wait_for_timeout(300)" not in focus_source
    assert 'input[type="radio"]' in focus_source
    assert "keyboard-focused radio proxy lacks a visible focus indicator" in focus_source

    styles = Path("src/dashboard/styles.py").read_text(encoding="utf-8")
    assert ':has(input[type="radio"]:focus-visible)' in styles
    assert 'data-testid="stExpandSidebarButton"' in styles
    assert 'data-testid="stSidebarCollapseButton"' in styles
    assert 'visibility: hidden !important;' in styles
    assert '[data-testid="stSidebar"][data-collapsed="true"] *' in styles


def test_browser_failure_evidence_is_structured_and_atomic(tmp_path: Path) -> None:
    (tmp_path / "failure-route-mobile.png").write_bytes(b"png")
    (tmp_path / "route-mobile.png").write_bytes(b"png")
    path = write_failure_evidence("http://127.0.0.1:8851", tmp_path, "mobile/route: console error")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["status"] == "failed"
    assert payload["base_url"] == "http://127.0.0.1:8851"
    assert "mobile/route" in payload["error"]
    assert payload["screenshots"] == ["failure-route-mobile.png", "route-mobile.png"]
    assert not (tmp_path / "failure-evidence.json.tmp").exists()

def test_browser_ci_retains_candidate_visual_evidence() -> None:
    workflow = Path(".github/workflows/quality.yml").read_text(encoding="utf-8")
    evidence = workflow.split("name: Retain browser visual acceptance evidence", 1)[1]
    assert "if: always()" in evidence
    assert "actions/upload-artifact@" in evidence
    assert "docs/screenshots/ui-qa/*.png" in evidence
    assert "docs/screenshots/ui-qa/failure-evidence.json" in evidence
    assert "github.run_attempt" in evidence

def test_native_navigation_reflows_current_framework_labels() -> None:
    styles = (ROOT / "src/dashboard/styles.py").read_text(encoding="utf-8")
    assert '.st-key-dashboard_view [role="radiogroup"]' in styles
    assert "repeat(auto-fit, minmax(min(100%, 8rem), 1fr))" in styles
    assert '.st-key-dashboard_view label' in styles
    assert "min-height: max(48px, 3rem) !important;" in styles
    assert '.st-key-dashboard_view label:has(input:checked)' in styles

def test_view_navigation_keeps_a_native_required_single_selection() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    navigation = app.split('selected_view = st.radio(', 1)[1].split(
        "render_active_view(", 1
    )[0]
    assert "index=0" in navigation
    assert "horizontal=True" in navigation
    assert 'key="dashboard_view"' in navigation

def test_layout_audit_covers_native_navigation_targets_and_labels() -> None:
    source = (ROOT / "scripts/ui_qa.py").read_text(encoding="utf-8")
    layout = source.split("def layout_issues(page)", 1)[1].split("def wait_for_app_idle", 1)[0]
    assert "textarea, .st-key-dashboard_view label" in layout
    assert ".st-key-dashboard_view label, .st-key-dashboard_view label p" in layout
    assert "interactive label is clipped" in layout
    assert "small interactive target" in layout

def test_dashboard_panels_are_not_limited_to_prose_width() -> None:
    styles = (ROOT / "src/dashboard/styles.py").read_text(encoding="utf-8")
    assert 'p, li, label, [data-testid="stMarkdownContainer"]' not in styles
    assert "p, li, label {{" in styles
    assert "clamp(1.75rem, 3vw, 3rem)" in styles
    assert "numeric signal is split across lines" in (ROOT / "scripts/ui_qa.py").read_text(encoding="utf-8")

def test_tablet_signal_grid_overrides_the_desktop_minimum_tracks() -> None:
    styles = (ROOT / "src/dashboard/styles.py").read_text(encoding="utf-8")
    assert "@media (max-width: 1100px) and (min-width: 641px)" in styles
    assert ".signal-deck {{ grid-template-columns: repeat(2, minmax(0, 1fr)) !important;" in styles
    assert ".signal-primary {{ grid-column: 1 / -1 !important; grid-row: auto !important;" in styles


class _ScrollPage:
    def __init__(self, total: int = 2100, top: int = 170) -> None:
        self.total = total
        self.top = top
        self.behavior = "smooth"
        self.shots = []

    def evaluate(self, script, command):
        assert '[data-testid="stMain"]' in script
        previous = self.behavior
        if command["action"] == "start":
            self.behavior = "auto"
        elif command["action"] in {"move", "restore"}:
            self.top = min(command["top"], max(0, self.total - 1000))
        if command["action"] == "restore":
            self.behavior = command["behavior"]
        return {"top": self.top, "height": 1000, "total": self.total,
                "behavior": previous}

    def wait_for_timeout(self, duration):
        assert duration == 150

    def screenshot(self, *, path, full_page):
        assert full_page is False
        self.shots.append(path)


def test_scroll_evidence_reaches_bottom_and_restores_original_position(tmp_path: Path) -> None:
    workflow = (ROOT / ".github/workflows/quality.yml").read_text(encoding="utf-8")
    assert "docs/screenshots/ui-qa/*-scroll.json" in workflow
    page = _ScrollPage()
    assert capture_scroll_evidence(page, tmp_path, "route-desktop") == []
    report = json.loads((tmp_path / "route-desktop-scroll.json").read_text())
    assert report["complete"] is True
    assert report["manual_visual_acceptance"] == "pending"
    assert [part["top"] for part in report["segments"]] == [0, 800, 1100]
    assert page.top == 170
    assert page.behavior == "smooth"
    assert len(page.shots) == 3


def test_scroll_evidence_handles_pages_shorter_than_the_viewport(tmp_path: Path) -> None:
    page = _ScrollPage(total=600, top=0)
    assert capture_scroll_evidence(page, tmp_path, "short") == []
    assert len(page.shots) == 1
    assert json.loads((tmp_path / "short-scroll.json").read_text())["complete"] is True


def test_scroll_evidence_limit_is_an_explicit_failure_not_silent_truncation(tmp_path: Path) -> None:
    page = _ScrollPage(total=1_000_000)
    issues = capture_scroll_evidence(page, tmp_path, "long")
    assert issues == ["scroll evidence limit reached before the page bottom"]
    assert len(page.shots) == SCROLL_EVIDENCE_MAX_SEGMENTS
    assert json.loads((tmp_path / "long-scroll.json").read_text())["complete"] is False
    assert page.top == 170
    assert page.behavior == "smooth"


def test_scroll_evidence_restores_scrollport_when_screenshot_fails(tmp_path: Path) -> None:
    import pytest

    page = _ScrollPage()

    def fail(**kwargs):
        raise RuntimeError("Screenshot failed")

    page.screenshot = fail
    with pytest.raises(RuntimeError, match="Screenshot failed"):
        capture_scroll_evidence(page, tmp_path, "failure")
    assert page.top == 170
    assert page.behavior == "smooth"
    assert json.loads((tmp_path / "failure-scroll.json").read_text())["complete"] is False


def test_download_labels_keep_palette_and_contrast_in_both_theme_modes() -> None:
    styles = (ROOT / "src/dashboard/styles.py").read_text(encoding="utf-8")
    qa = (ROOT / "scripts/ui_qa.py").read_text(encoding="utf-8")
    assert '[data-testid="stDownloadButton"] button {{\n            background-color: var(--surface) !important;\n            color: var(--text) !important;' in styles
    assert '[data-testid="stDownloadButton"] button p {{\n            color: inherit !important;' in styles
    assert "download label contrast below 4.5:1" in qa
    assert "button.disabled" in qa
    assert "0.2126, 0.7152, 0.0722" in qa
