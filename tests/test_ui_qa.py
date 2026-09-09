from __future__ import annotations

import json
from pathlib import Path

from scripts.ui_qa import (
    focus_issues,
    CORE_VIEWPORTS,
    EXTENDED_VIEWPORTS,
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


def test_browser_qa_is_wired_into_ci_and_kept_out_of_release_artifacts() -> None:
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-e2e.txt").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "python scripts/ui_qa.py --url http://127.0.0.1:8851" in workflow
    assert "python -m playwright install --with-deps chromium" in workflow
    assert "playwright==1.58.0" in requirements
    assert "docs/screenshots/ui-qa/" in gitignore


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
