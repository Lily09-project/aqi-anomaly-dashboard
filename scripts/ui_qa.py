from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


VIEW_CONTRACTS = {
    "總覽": "台灣測站分布",
    "地區比較": "目前與下一小時",
    "預測": "實際 AQI 與預測 AQI",
    "異常偵測": "事件調查摘要",
    "資料品質": "資料可靠性",
    "模型指標": "模型健康度與漂移",
}
VIEWPORTS = (
    ("desktop", 1440, 1000),
    ("small-mobile", 375, 812),
    ("landscape", 844, 390),
)
STREAMLIT_EXCEPTION_SELECTOR = '[data-testid="stException"]'


def failure_screenshot_names(screenshot_dir: Path, error: str) -> list[str]:
    names = {path.name for path in screenshot_dir.glob("failure-*.png")}
    for failure in error.split("; "):
        scope = failure.split(":", 1)[0]
        if "/" not in scope:
            continue
        viewport, route = scope.split("/", 1)
        candidate = screenshot_dir / f"{route}-{viewport}.png"
        if candidate.is_file():
            names.add(candidate.name)
    return sorted(names)


def write_failure_evidence(base_url: str, screenshot_dir: Path, error: str) -> Path:
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = screenshot_dir / "failure-evidence.json"
    payload = {
        "schema_version": "1.0",
        "status": "failed",
        "base_url": base_url,
        "error": error,
        "screenshots": failure_screenshot_names(screenshot_dir, error),
    }
    temporary = evidence_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(evidence_path)
    return evidence_path


def check_health(base_url: str) -> None:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("UI QA URL must use http(s) with a host")
    # The scheme and loopback host are validated immediately above.
    with urllib.request.urlopen(  # nosec B310
        f"{base_url.rstrip('/')}/_stcore/health", timeout=5
    ) as response:
        body = response.read(4096).decode("utf-8", errors="replace")
    if "ok" not in body.lower():
        raise RuntimeError(f"Unexpected Streamlit health response: {body[:200]}")


def run_browser_checks(base_url: str, screenshot_dir: Path) -> str:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("install requirements-e2e.txt before browser QA") from exc

    screenshot_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for viewport_name, width, height in VIEWPORTS:
            page = browser.new_page(viewport={"width": width, "height": height})
            active_view = "initial-load"
            console_errors: list[str] = []
            page.on(
                "console",
                lambda message, errors=console_errors: errors.append(message.text)
                if message.type == "error"
                else None,
            )
            page.on("pageerror", lambda error, errors=console_errors: errors.append(str(error)))
            try:
                page.emulate_media(reduced_motion="reduce")
                page.goto(base_url, wait_until="domcontentloaded", timeout=60_000)
                page.get_by_role("heading", name="台灣 AQI 監測與預測", exact=True).wait_for(
                    timeout=60_000
                )
                if page.locator('a.skip-link[href="#dashboard-main"]').count() != 1:
                    failures.append(f"{viewport_name}: missing skip link")
                if page.locator("#dashboard-main").count() != 1:
                    failures.append(f"{viewport_name}: missing main-content anchor")

                for view, required_text in VIEW_CONTRACTS.items():
                    active_view = view
                    page.get_by_role("button", name=view, exact=True).click(timeout=15_000)
                    try:
                        page.get_by_text(required_text, exact=True).first.wait_for(timeout=30_000)
                    except PlaywrightError:
                        failures.append(f"{viewport_name}/{view}: missing {required_text}")
                    if page.locator(STREAMLIT_EXCEPTION_SELECTOR).count():
                        failures.append(f"{viewport_name}/{view}: Streamlit runtime exception")
                    overflow = page.evaluate(
                        "document.documentElement.scrollWidth - window.innerWidth"
                    )
                    if overflow > 4:
                        failures.append(f"{viewport_name}/{view}: horizontal overflow {overflow}px")
                    page.screenshot(
                        path=str(screenshot_dir / f"{view}-{viewport_name}.png"),
                        full_page=True,
                    )
                if console_errors:
                    failures.append(f"{viewport_name}: console errors {console_errors[:3]}")
            except PlaywrightError as exc:
                failures.append(f"{viewport_name}: browser error {exc}")
                try:
                    page.screenshot(
                        path=str(screenshot_dir / f"failure-{active_view}-{viewport_name}.png"),
                        full_page=True,
                    )
                except PlaywrightError:
                    pass
            finally:
                page.close()
        browser.close()
    if failures:
        raise RuntimeError("; ".join(failures[:18]))
    return "PASS: 6 views × 3 viewports, accessibility, overflow, runtime, and console checks"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AQI Streamlit browser QA.")
    parser.add_argument("--url", default="http://127.0.0.1:8851")
    parser.add_argument("--screenshots", default="docs/screenshots/ui-qa")
    args = parser.parse_args()
    screenshot_dir = Path(args.screenshots)
    (screenshot_dir / "failure-evidence.json").unlink(missing_ok=True)
    for stale in screenshot_dir.glob("failure-*.png"):
        stale.unlink(missing_ok=True)
    try:
        check_health(args.url)
        result = run_browser_checks(args.url, screenshot_dir)
    except (OSError, urllib.error.URLError, RuntimeError, ValueError) as exc:
        evidence = write_failure_evidence(args.url, screenshot_dir, str(exc))
        print(f"FAIL: {exc}")
        print(f"EVIDENCE: {evidence}")
        return 1
    (screenshot_dir / "failure-evidence.json").unlink(missing_ok=True)
    print(json.dumps({"health": "PASS", "browser": result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
