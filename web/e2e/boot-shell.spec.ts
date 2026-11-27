import { expect, openRoute, test } from "./fixtures";

// The static loading shell in index.html gives slow phones something to look at while the script downloads.
test.describe("static boot shell", () => {
  test("is in the served HTML, so it paints before any script runs", async ({ page }) => {
    const html = await (await page.request.get("./")).text();
    expect(html).toContain('class="boot"');
    expect(html).toContain("Taiwan Air Lab");
    // Without JavaScript the page keeps its <noscript> message instead of an endless loading state.
    expect(html).toMatch(/<noscript><style>\s*\.boot\s*\{\s*display:\s*none\s*!important;?\s*\}\s*<\/style><\/noscript>/);
  });

  test("is replaced by the app once React mounts, leaving no loading shell and no layout shift", async ({ page }) => {
    await page.addInitScript(() => {
      (window as unknown as { __cls: number }).__cls = 0;
      new PerformanceObserver((list) => {
        for (const entry of list.getEntries() as unknown as { value: number; hadRecentInput: boolean }[]) {
          if (!entry.hadRecentInput) (window as unknown as { __cls: number }).__cls += entry.value;
        }
      }).observe({ type: "layout-shift", buffered: true });
    });
    await openRoute(page, "/");
    await expect(page.locator(".boot")).toHaveCount(0);
    await expect(page.getByRole("navigation", { name: "主要頁面" })).toBeVisible();
    await page.waitForTimeout(500);
    const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
    expect(cls).toBeLessThan(0.01);
  });
});
