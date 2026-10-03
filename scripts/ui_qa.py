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
CORE_VIEWPORTS = (
    ("desktop", 1440, 1000),
    ("small-mobile", 375, 812),
    ("tablet", 768, 1024),
    ("landscape", 844, 390),
    ("wide-tablet", 1024, 768),
)
EXTENDED_VIEWPORTS = (
    ("tiny-mobile", 320, 568),
    ("large-mobile", 414, 896),
)
VIEWPORTS = CORE_VIEWPORTS
STREAMLIT_EXCEPTION_SELECTOR = '[data-testid="stException"]'
TEXT_SCALE_CSS = ":root { font-size: 200% !important; }"
THEME_OPTION_LABELS = {"light":"霧白藍（淺色）","dark":"午夜藍"}
# WCAG-friendly touch target floor for user-facing controls. Streamlit's
# internal toolbar/header controls are explicitly excluded below.
MIN_INTERACTIVE_TARGET_PX = 44


def viewport_matrix(extended: bool = False) -> tuple[tuple[str, int, int], ...]:
    return CORE_VIEWPORTS + EXTENDED_VIEWPORTS if extended else CORE_VIEWPORTS


def layout_issues(page) -> list[str]:
    """Return observable layout/accessibility defects from the rendered page."""
    return page.evaluate(
        """() => {
            const issues = [];
            const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0 && rect.height > 0 && style.display !== 'none'
                    && style.visibility !== 'hidden';
            };
            const heading = document.querySelector('#dashboard-main h1, main h1, h1');
            if (!heading || !visible(heading)) {
                issues.push('main heading is missing or hidden');
            } else {
                const rect = heading.getBoundingClientRect();
                const inViewport = rect.bottom > 0 && rect.top < window.innerHeight;
                if (inViewport) {
                    const x = Math.min(window.innerWidth - 1, Math.max(1, rect.left + rect.width / 2));
                    const y = Math.min(window.innerHeight - 1, Math.max(1, rect.top + rect.height / 2));
                    const top = document.elementFromPoint(x, y);
                    if (!top || (!heading.contains(top) && !top.contains(heading))) {
                        issues.push('main heading is obscured');
                    }
                }
            }
            for (const control of document.querySelectorAll('button[data-testid^="stBaseButton"], [data-testid="stButton"] button, select, textarea')) {
                if (!visible(control)) continue;
                const rect = control.getBoundingClientRect();
                const inViewport = rect.right > 0 && rect.left < window.innerWidth
                    && rect.bottom > 0 && rect.top < window.innerHeight;
                const testId = control.getAttribute('data-testid') || '';
                if (!inViewport || testId === 'stBaseButton-elementToolbar'
                    || testId.startsWith('stBaseButton-header')) continue;
                if (rect.width < 44 || rect.height < 44) {
                    const label = (control.innerText || control.getAttribute('aria-label') || '').trim().slice(0, 80);
                    issues.push(`small interactive target: ${testId || control.tagName} ${Math.round(rect.width)}x${Math.round(rect.height)} ${label}`.trim());
                    break;
                }
            }
            for (const element of document.querySelectorAll('button, [role="button"]')) {
                if (!visible(element)) continue;
                const style = getComputedStyle(element);
                if ((style.overflow === 'hidden' || style.overflowX === 'hidden' || style.overflowY === 'hidden')
                    && (element.scrollWidth > element.clientWidth + 3 || element.scrollHeight > element.clientHeight + 3)) {
                    const label = (element.innerText || element.getAttribute('aria-label') || '').trim().slice(0, 80);
                    const testId = element.getAttribute('data-testid') || '';
                    issues.push(`interactive label is clipped: ${testId || element.tagName} ${label}`.trim());
                    break;
                }
            }
            return issues;
        }"""
    )


def focus_issues(page) -> list[str]:
    """Traverse real Tab order, validating visible controls and their focused proxies."""
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

    issues: list[str] = []
    page.evaluate(
        """() => {
            document.activeElement?.blur();
            document.body.setAttribute('tabindex', '-1');
            document.body.focus();
            document.body.removeAttribute('tabindex');
            window.scrollTo(0, 0);
        }"""
    )
    reached_skip_link = False
    reached_interactive_control = False
    visited: set[str] = set()
    visited_order: list[str] = []

    for _attempt in range(24):
        page.keyboard.press("Tab")
        try:
            page.wait_for_function(
                """() => {
                    const target = document.activeElement;
                    if (!target || !target.matches('a.skip-link')) return true;
                    if (!target.matches(':focus-visible')) return false;
                    const transform = getComputedStyle(target).transform;
                    return transform === 'none'
                        || Math.abs(new DOMMatrixReadOnly(transform).m42) < 1;
                }""",
                timeout=2_000,
            )
        except PlaywrightTimeoutError:
            pass

        state = page.evaluate(
            """() => {
                const inViewport = rect => rect.right > 0 && rect.left < window.innerWidth
                    && rect.bottom > 0 && rect.top < window.innerHeight;
                const rendered = element => {
                    if (!element || !(element instanceof Element)) return false;
                    const rect = element.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) return false;
                    for (let node = element; node && node instanceof HTMLElement; node = node.parentElement) {
                        const style = getComputedStyle(node);
                        if (style.display === 'none' || style.visibility === 'hidden'
                                || Number(style.opacity) === 0) return false;
                    }
                    return true;
                };
                const target = document.activeElement;
                if (!target || target === document.body) {
                    return {key: '', skipLink: false, interactive: false, issue: ''};
                }

                const targetRect = target.getBoundingClientRect();
                const targetStyle = getComputedStyle(target);
                const isRadio = target.matches('input[type="radio"]');
                const radioItem = isRadio
                    ? target.closest('[data-baseweb="radio"], [role="radio"], label')
                    : null;
                const radioWidget = isRadio
                    ? target.closest('[data-testid="stRadio"], [role="radiogroup"], [data-baseweb="radio"]')
                    : null;
                const associatedLabel = isRadio
                    ? Array.from(target.labels || []).find(label => rendered(label))
                    : null;
                const proxy = associatedLabel || radioItem;
                const proxyText = proxy
                    ? (proxy.getAttribute('aria-label') || proxy.innerText || proxy.textContent || '').trim()
                    : '';
                const namedProxy = Boolean(proxy && (
                    proxy.getAttribute('aria-label') || proxy.getAttribute('aria-labelledby') || proxyText
                ));
                const hiddenRadioInput = isRadio && (
                    targetRect.width <= 1 || targetRect.height <= 1
                    || targetStyle.display === 'none' || targetStyle.visibility === 'hidden'
                    || Number(targetStyle.opacity) === 0 || !inViewport(targetRect)
                );
                const usesProxy = Boolean(
                    hiddenRadioInput && radioWidget && radioItem && proxy && proxy !== target
                    && namedProxy && rendered(proxy)
                );
                const visualTarget = usesProxy ? proxy : target;
                const rect = visualTarget.getBoundingClientRect();
                const style = getComputedStyle(visualTarget);
                const details = JSON.stringify({
                    focusedTag: target.tagName,
                    focusedRect: [Math.round(targetRect.left), Math.round(targetRect.top),
                        Math.round(targetRect.right), Math.round(targetRect.bottom)],
                    visibleTarget: visualTarget.tagName,
                    label: proxyText.slice(0, 80),
                    visibleRect: [Math.round(rect.left), Math.round(rect.top),
                        Math.round(rect.right), Math.round(rect.bottom)],
                    display: style.display,
                    visibility: style.visibility,
                    position: style.position,
                    transform: style.transform,
                });
                const key = [
                    target.tagName, target.id || '', target.getAttribute('data-testid') || '',
                    target.getAttribute('aria-label') || '', target.type || '', target.value || '',
                    proxyText.slice(0, 80), (target.textContent || '').trim().slice(0, 40),
                ].join('|');

                if (!rendered(visualTarget)) {
                    const message = usesProxy ? 'radio proxy is hidden' : 'keyboard-focused target is hidden';
                    return {key, skipLink: false, interactive: false, issue: message + ' (' + details + ')'};
                }
                if (!inViewport(rect)) {
                    return {key, skipLink: false, interactive: false, issue: 'keyboard-focused target is outside viewport (' + details + ')'};
                }
                if (!target.matches(':focus-visible')) {
                    return {key, skipLink: false, interactive: false, issue: 'keyboard-focused target lacks focus-visible state (' + details + ')'};
                }
                if (usesProxy) {
                    const width = Number.parseFloat(style.outlineWidth || '0');
                    const color = style.outlineColor;
                    if (width < 2 || style.outlineStyle === 'none'
                            || color === 'transparent' || color === 'rgba(0, 0, 0, 0)') {
                        return {
                            key,
                            skipLink: false,
                            interactive: false,
                            issue: 'keyboard-focused radio proxy lacks a visible focus indicator (' + details + ')',
                        };
                    }
                }

                const x = Math.min(window.innerWidth - 1, Math.max(1, rect.left + rect.width / 2));
                const y = Math.min(window.innerHeight - 1, Math.max(1, rect.top + rect.height / 2));
                const top = document.elementFromPoint(x, y);
                const widget = visualTarget.closest('[data-baseweb], [data-testid], [role="radiogroup"]');
                const topWidget = top?.closest('[data-baseweb], [data-testid], [role="radiogroup"]');
                const unobscured = usesProxy
                    ? Boolean(top && (visualTarget.contains(top) || top.contains(visualTarget)))
                    : Boolean(top && (
                        visualTarget.contains(top) || top.contains(visualTarget)
                        || (widget && topWidget && widget === topWidget)
                    ));
                if (!unobscured) {
                    return {key, skipLink: false, interactive: false, issue: 'keyboard-focused target is obscured (' + details + ')'};
                }

                const skipLink = visualTarget.matches('a.skip-link');
                const interactive = usesProxy || (
                    !skipLink && target.matches(
                        'a[href], button, input, select, textarea, [role="button"], [tabindex]'
                    )
                );
                return {key, skipLink, interactive, issue: ''};
            }"""
        )
        key = str(state.get("key", ""))
        if not key or key in visited:
            continue
        visited.add(key)
        visited_order.append(key)
        if state.get("issue"):
            issues.append(f"{state['issue']}: {key}")
        reached_skip_link = reached_skip_link or bool(state.get("skipLink"))
        reached_interactive_control = reached_interactive_control or bool(
            state.get("interactive")
        )
        if reached_skip_link and reached_interactive_control:
            break

    if not reached_skip_link:
        traversal = " -> ".join(visited_order[:8]) or "(none)"
        issues.append(f"keyboard focus did not reach the skip link; visited: {traversal}")
    if not reached_interactive_control:
        issues.append("keyboard focus did not reach an interactive control")
    return issues

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


def apply_theme_mode(
    page,
    theme_mode: str | None,
    *,
    selector_label: str | None = None,
    option_labels: dict[str, str] | None = None,
) -> None:
    if theme_mode is None:
        return
    if theme_mode not in {"light", "dark"}:
        raise ValueError("theme_mode must be light or dark")
    if selector_label is not None:
        sidebar = page.locator('[data-testid="stSidebar"]')
        if sidebar.get_attribute("aria-expanded") != "true":
            expand_control = page.locator('[data-testid="stExpandSidebarButton"]')
            expand_button = expand_control.locator("button")
            if expand_button.count():
                expand_button.click(timeout=15_000)
            else:
                expand_control.click(timeout=15_000)
        option_label = (option_labels or {}).get(theme_mode)
        if not option_label:
            raise ValueError(f"missing app theme label for {theme_mode}")
        page.get_by_role("combobox", name=selector_label).click(timeout=15_000)
        page.get_by_role("option", name=option_label, exact=True).click(timeout=15_000)
        collapse_button = page.locator('[data-testid="stSidebarCollapseButton"] button')
        if sidebar.get_attribute("aria-expanded") == "true" and collapse_button.count():
            collapse_button.click(timeout=15_000)
    page.wait_for_function(
        "expected => getComputedStyle(document.documentElement).colorScheme === expected",
        arg=theme_mode,
        timeout=15_000,
    )


def download_payload(page, label: str, suffix: str) -> bytes:
    """Read the real browser download, not the button's presence or URL."""
    with page.expect_download(timeout=30_000) as pending:
        page.get_by_role("button", name=label, exact=True).click(timeout=30_000)
    download = pending.value
    failure = download.failure()
    if failure or not download.suggested_filename.endswith(suffix):
        raise RuntimeError(f"download failed or unexpected filename: {label}: {failure}")
    path = download.path()
    if path is None:
        raise RuntimeError(f"download has no readable payload: {label}")
    payload = Path(path).read_bytes()
    if not payload:
        raise RuntimeError(f"download is empty: {label}")
    return payload


def open_sidebar(page) -> None:
    sidebar = page.locator('[data-testid="stSidebar"]')
    if sidebar.get_attribute("aria-expanded") != "true":
        control = page.locator('[data-testid="stExpandSidebarButton"]')
        button = control.locator("button")
        (button if button.count() else control).click(timeout=15_000)
    page.wait_for_function(
        "() => document.querySelector('[data-testid=stSidebar]')?.getAttribute('aria-expanded') === 'true'",
        timeout=15_000,
    )


def choose_option(page, label: str, value: str) -> None:
    selector = page.get_by_role("combobox", name=label, exact=True)
    selector.scroll_into_view_if_needed()
    selector.click()
    page.get_by_role("option", name=value, exact=True).click()
    page.keyboard.press("Escape")


def functional_download_smoke(page, base_url: str, theme_mode: str | None) -> None:
    import csv
    from datetime import date
    from io import StringIO

    page.goto(base_url, wait_until="domcontentloaded", timeout=60_000)
    page.get_by_role("heading", name="台灣 AQI 監測與預測", exact=True).wait_for(timeout=60_000)
    apply_theme_mode(page, theme_mode, selector_label="選擇介面主題", option_labels=THEME_OPTION_LABELS)
    open_sidebar(page)
    choose_option(page, "縣市", "臺北市")
    choose_option(page, "測站", "松山測站")
    choose_option(page, "時間範圍", "自訂日期")
    page.locator(".st-key-custom_date_range").wait_for()
    page.get_by_text("下載", exact=True).click()
    csv_payload = download_payload(page, "下載目前篩選資料 (.csv)", ".csv")
    report = json.loads(download_payload(page, "下載可靠性摘要 (.json)", ".json"))
    rows = list(csv.DictReader(StringIO(csv_payload.decode("utf-8-sig"))))
    if not rows or {row["縣市"] for row in rows} != {"臺北市"} or {row["測站"] for row in rows} != {"松山測站"}:
        raise RuntimeError("AQI exported CSV does not match selected county/station")
    selection = report["selection"]
    if selection["county"] != "臺北市" or selection["station"] != "松山測站":
        raise RuntimeError("AQI reliability JSON lost filter metadata")
    start, end = date.fromisoformat(selection["start_date"]), date.fromisoformat(selection["end_date"])
    if any(not start <= date.fromisoformat(row["時間"][:10].replace("/", "-")) <= end for row in rows):
        raise RuntimeError("AQI exported CSV contains dates outside the selected range")
    if report["data_quality"]["rows"] != len(rows) or report["data_quality"]["station_count"] != 1:
        raise RuntimeError("AQI reliability JSON disagrees with the exported observations")


def run_browser_checks(
    base_url: str,
    screenshot_dir: Path,
    extended: bool = False,
    text_scale: bool = False,
    theme_mode: str | None = None,
) -> str:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("install requirements-e2e.txt before browser QA") from exc

    screenshot_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for viewport_name, width, height in viewport_matrix(extended):
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
                if theme_mode is None:
                    page.emulate_media(reduced_motion="reduce")
                else:
                    page.emulate_media(reduced_motion="reduce", color_scheme=theme_mode)
                page.goto(base_url, wait_until="domcontentloaded", timeout=60_000)
                page.get_by_role("heading", name="台灣 AQI 監測與預測", exact=True).wait_for(
                    timeout=60_000
                )
                apply_theme_mode(
                    page,
                    theme_mode,
                    selector_label="選擇介面主題",
                    option_labels=THEME_OPTION_LABELS,
                )
                if text_scale:
                    page.add_style_tag(content=TEXT_SCALE_CSS)
                    page.wait_for_timeout(250)
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
                    for issue in layout_issues(page):
                        failures.append(f"{viewport_name}/{view}: {issue}")
                    for issue in focus_issues(page):
                        failures.append(f"{viewport_name}/{view}: {issue}")
                    page.evaluate("document.activeElement?.blur()")
                    suffix = "-text-200" if text_scale else ""
                    page.screenshot(
                        path=str(screenshot_dir / f"{view}-{viewport_name}{suffix}.png"),
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

        for flow_name, flow_width, flow_height in (
            ("desktop", 1440, 1000),
            ("mobile", 320 if extended else 375, 812),
        ):
            flow_page = browser.new_page(viewport={"width": flow_width, "height": flow_height}, accept_downloads=True)
            try:
                if theme_mode is None:
                    flow_page.emulate_media(reduced_motion="reduce")
                else:
                    flow_page.emulate_media(reduced_motion="reduce", color_scheme=theme_mode)
                functional_download_smoke(flow_page, base_url, theme_mode)
                if flow_page.locator(STREAMLIT_EXCEPTION_SELECTOR).count():
                    failures.append(f"{flow_name}/downloads: Streamlit runtime exception")
            except (PlaywrightError, RuntimeError, ValueError, OSError) as exc:
                failures.append(f"{flow_name}/downloads: {exc}")
                flow_page.screenshot(path=str(screenshot_dir / f"failure-downloads-{flow_name}.png"), full_page=True)
            finally:
                flow_page.close()
        browser.close()
    if failures:
        raise RuntimeError("; ".join(failures[:18]))
    text_note = ", 200% text reflow" if text_scale else ""
    return f"PASS: {len(VIEW_CONTRACTS)} views × {len(viewport_matrix(extended))} viewports, accessibility, overflow, runtime, and console checks{text_note}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AQI Streamlit browser QA.")
    parser.add_argument("--url", default="http://127.0.0.1:8851")
    parser.add_argument("--screenshots", default="docs/screenshots/ui-qa")
    parser.add_argument(
        "--extended",
        action="store_true",
        help="also run 320px and 414px mobile viewports",
    )
    parser.add_argument(
        "--text-scale",
        action="store_true",
        help="apply 200% root text scaling and rerun reflow checks",
    )
    parser.add_argument("--theme-mode", choices=("light", "dark"))
    args = parser.parse_args()
    screenshot_dir = Path(args.screenshots)
    (screenshot_dir / "failure-evidence.json").unlink(missing_ok=True)
    for stale in screenshot_dir.glob("failure-*.png"):
        stale.unlink(missing_ok=True)
    try:
        check_health(args.url)
        result = run_browser_checks(
            args.url,
            screenshot_dir,
            extended=args.extended,
            text_scale=args.text_scale,
            theme_mode=args.theme_mode,
        )
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
