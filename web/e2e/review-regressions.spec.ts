import { expect, fetchJson, openRoute, test } from "./fixtures";

// Regressions found by the full code review and the user-journey pass (2026-11).
interface Overview {
  stations: { station: string }[];
}

test.describe("review regressions", () => {
  test("the station page lists the duration from the URL instead of showing 1 hour", async ({ page }) => {
    const overview = await fetchJson<Overview>(page, "overview.json");
    const name = overview.stations[0]!.station;
    // 5 is valid in the URL (1–12) but is not one of the preset choices.
    await openRoute(page, `/station/${encodeURIComponent(name)}?hours=5`);
    await expect(page.getByLabel("活動時長")).toHaveValue("5");
    await expect(page.getByLabel("活動時長").locator("option:checked")).toHaveText("5 小時");
  });

  test("switching the station keeps keyboard focus on the switcher", async ({ page }) => {
    const overview = await fetchJson<Overview>(page, "overview.json");
    test.skip(overview.stations.length < 2, "needs at least two locations");
    // Browsers pause animation frames in background tabs; focus must not depend on them.
    await page.addInitScript(() => { window.requestAnimationFrame = () => 0; });
    const [first, second] = overview.stations.map((s) => s.station) as [string, string];
    await openRoute(page, `/station/${encodeURIComponent(first)}`);
    const switcher = page.getByLabel(/切換/).first();
    await switcher.focus();
    // Real keyboard input: programmatic selectOption does not behave like a person using the arrow keys.
    const options = await switcher.locator("option").allInnerTexts();
    const step = options.indexOf(second) > options.indexOf(first) ? "ArrowDown" : "ArrowUp";
    await page.keyboard.press(step);
    await expect(page.locator("h1")).toHaveText(options[options.indexOf(first) + (step === "ArrowDown" ? 1 : -1)]!);
    await expect(page.locator("#station-switch")).toBeFocused();
  });

  test("picking an event moves focus to its detail, in view on a phone", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openRoute(page, "/anomalies");
    const items = page.locator("[data-testid=event-list] a.event-item");
    test.skip((await items.count()) < 3, "needs at least three events");
    await items.nth(2).scrollIntoViewIfNeeded();
    await items.nth(2).click();
    await expect(page.locator("#event-detail")).toBeFocused();
    await expect(page.locator("#event-detail")).toBeInViewport();
  });

  test("the what-if headline never shows a negative AQI", async ({ page }) => {
    await openRoute(page, "/whatif");
    for (const key of ["aqi_now", "pm25_now", "pm10_now"]) {
      const slider = page.locator(`#whatif-${key}`);
      await slider.fill((await slider.getAttribute("min")) ?? "0");
    }
    const headline = (await page.getByTestId("whatif-prediction").innerText()).trim();
    expect(headline).toMatch(/^\d/);
    expect(await page.getByTestId("whatif-interval").innerText()).not.toContain("-");
    // Only the short status line is announced while a slider moves, not the whole panel.
    await expect(page.locator(".whatif-result[aria-live]")).toHaveCount(0);
    await expect(page.locator(".whatif-result [role=status]")).toHaveCount(1);
  });

  test("the replay button is labelled play/pause without also being a pressed toggle", async ({ page }) => {
    await openRoute(page, "/propagation");
    const play = page.getByRole("button", { name: "播放" });
    await expect(play).not.toHaveAttribute("aria-pressed", /.*/);
    await play.click();
    await expect(page.getByRole("button", { name: /暫停/ })).not.toHaveAttribute("aria-pressed", /.*/);
  });
});
