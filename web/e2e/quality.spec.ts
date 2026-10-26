import { expect, expectAccessible, openRoute, test } from "./fixtures";

const ROUTES = [
  "/",
  "/station/前金測站",
  "/propagation",
  "/anomalies",
  "/whatif",
  "/model",
  "/data",
];
const FIXED_BACKGROUND = "#f2f5f6";
const LEGACY_THEME_KEY = "taiwan-air-lab-theme";

test.describe("Q4/Q5 navigation, keyboard and accessibility", () => {
  test("skip link and keyboard-only navigation reach every page", async ({ page }) => {
    await openRoute(page, "/");
    await page.keyboard.press("Tab");
    await expect(page.getByText("跳到主要內容")).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("main")).toBeFocused();
    await expect(page.locator("main")).toHaveCSS("outline-style", "solid");
    await expect(page.locator("main")).toHaveCSS("outline-width", "3px");

    // A map station is a real link: focus it and press Enter.
    const marker = page.locator(".taiwan-map a").first();
    await marker.focus();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#\/station\//);
    await expect(page.locator("main")).toBeFocused();
  });

  test("navigation links move focus to the new page and mark the current page", async ({ page }) => {
    await openRoute(page, "/");
    const nav = page.getByRole("navigation", { name: "主要頁面" });
    await nav.getByRole("link", { name: "模型監控" }).click();
    await expect(page.locator("h1")).toHaveText("模型監控");
    await expect(nav.getByRole("link", { name: "模型監控" })).toHaveAttribute("aria-current", "page");
    await expect(page.locator("main")).toBeFocused();
    await expect(page).toHaveTitle(/模型監控/);
  });

  test("motion duration stays unchanged under reduced-motion system preference", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openRoute(page, "/");
    const durationMs = await page.locator(":root").evaluate((root) => {
      const value = getComputedStyle(root).getPropertyValue("--duration").trim();
      return value.endsWith("ms") ? Number.parseFloat(value) : Number.parseFloat(value) * 1000;
    });
    expect(durationMs).toBe(220);
  });

  test("every page keeps one palette under both system color preferences", async ({ page }) => {
    await page.addInitScript((key) => {
      try {
        window.localStorage.setItem(key, "dark");
      } catch {
        // Storage restrictions must not change the fixed site palette.
      }
    }, LEGACY_THEME_KEY);

    for (const colorScheme of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme });
      for (const route of ROUTES) {
        await openRoute(page, route);
        await page.locator(".state-loading").waitFor({ state: "detached" });
        await expect(page.getByLabel("介面主題")).toHaveCount(0);
        const appearance = await page.locator("html").evaluate((root) => ({
          dataTheme: root.getAttribute("data-theme"),
          colorScheme: getComputedStyle(root).colorScheme,
          background: getComputedStyle(root).getPropertyValue("--bg").trim(),
        }));
        expect(appearance).toEqual({
          dataTheme: null,
          colorScheme: "light",
          background: FIXED_BACKGROUND,
        });
        await expectAccessible(page);
      }
    }
  });



  test("unknown routes and stations render helpful empty states", async ({ page }) => {
    await page.goto("./#/nowhere");
    await expect(page.getByText("找不到這個頁面")).toBeVisible();
    await page.goto("./#/station/不存在測站");
    await expect(page.getByText("找不到這個測站")).toBeVisible();
    await expectAccessible(page);
  });

  test("every chart offers an equivalent data table", async ({ page }) => {
    for (const route of ROUTES) {
      await openRoute(page, route);
      const figures = page.locator("figure.chart-frame");
      const count = await figures.count();
      if (route === "/data") continue;
      expect(count, `charts on ${route}`).toBeGreaterThan(0);
      await expect(page.locator("figure.chart-frame details table")).toHaveCount(count);
    }
  });

  test("layout never scrolls horizontally", async ({ page }) => {
    for (const route of ROUTES) {
      await openRoute(page, route);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow, `horizontal overflow on ${route}`).toBeLessThanOrEqual(0);
    }
  });
});

test.describe("Q6 performance and Q8 security", () => {
  test("main content appears within 1.5 s and no third-party request is made", async ({ page }) => {
    const hosts = new Set<string>();
    page.on("request", (r) => hosts.add(new URL(r.url()).host));
    const start = Date.now();
    await page.goto("./");
    await expect(page.locator("main h1")).toBeVisible();
    expect(Date.now() - start).toBeLessThan(1500);
    await page.waitForLoadState("networkidle");
    expect([...hosts]).toEqual([new URL(page.url()).host]);
  });

  test("a strict Content-Security-Policy is declared and no inline script exists", async ({ page }) => {
    await page.goto("./");
    const csp = await page.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute("content");
    expect(csp).toContain("script-src 'self'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).not.toContain("unsafe-eval");
    expect(await page.locator("script:not([src])").count()).toBe(0);
  });
});
