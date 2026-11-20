import { expect, expectAccessible, openRoute, test } from "./fixtures";

test("兩地出門規劃 keeps settings after reload", async ({ page }) => {
  await openRoute(page, "/planner");
  await expect(page.getByRole("heading", { name: "兩地出門規劃" })).toBeVisible();
  await page.getByLabel("連續時數").selectOption("1");
  await page.getByLabel("AQI 門檻").selectOption("150");
  await page.getByLabel("判讀條件").selectOption("upper");
  await expect(page).toHaveURL(/rule=upper/);
  await page.reload();
  await expect(page.getByLabel("AQI 門檻")).toHaveValue("150");
  await expect(page.getByLabel("判讀條件")).toHaveValue("upper");
  const date = new Date("2030-01-01T00:00:00Z");
  await page.clock.setFixedTime(date);
  await page.reload();
  await expect(page.getByText(/共同預報時數不足|暫停提供共同時段/)).toBeVisible();
  await expect(page.getByRole("button", { name: "下載共同時段 CSV" })).toHaveCount(0);
});

test("兩地出門規劃 shows controls in a row, a chart of both forecasts and a compact list", async ({ page }) => {
  // Fixture forecasts start 2026-10-21 00:00 Taiwan time; stand just before them.
  await page.clock.install({ time: new Date("2026-10-20T15:30:00Z") });
  await openRoute(page, "/planner?a=%E6%9D%BE%E5%B1%B1%E6%B8%AC%E7%AB%99&b=%E5%89%8D%E9%87%91%E6%B8%AC%E7%AB%99&hours=1&threshold=500");
  await expect(page.locator(".page-head .lede")).toBeVisible();
  await expect(page.getByTestId("first-window")).toHaveText(/^\d+\/\d+ \d{2}:00–(\d+\/\d+ )?\d{2}:00$/);
  const figure = page.locator("figure.chart-frame");
  await expect(figure).toHaveCount(1);
  await expect(figure.locator("details table tbody tr")).not.toHaveCount(0);
  const list = page.getByTestId("planner-windows-table").locator("tbody tr");
  await expect(list).toHaveCount(6);
  await page.getByRole("button", { name: /顯示全部 \d+ 個時段/ }).click();
  expect(await list.count()).toBeGreaterThan(6);
  await page.getByText("查看最早時段的逐時預測").click();
  await expect(page.getByRole("region", { name: "最早時段的逐時預測" }).locator("tbody tr")).toHaveCount(1);

  if (page.viewportSize()!.width >= 900) {
    const tops = await page.locator(".planner-form select").evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().top)));
    expect(new Set(tops).size, "all five controls share one row").toBe(1);
  }

  // Control changes replace the history entry instead of stacking one per select.
  const length = await page.evaluate(() => history.length);
  await page.getByLabel("判讀條件").selectOption("upper");
  await page.getByLabel("連續時數").selectOption("2");
  await expect(page).toHaveURL(/hours=2.*rule=upper|rule=upper.*hours=2/);
  expect(await page.evaluate(() => history.length)).toBe(length);

  // Picking B's location for A swaps the two instead of comparing a place with itself.
  await page.getByLabel("地點 A").selectOption("前金測站");
  await expect(page.getByLabel("地點 B")).toHaveValue("松山測站");
  await expectAccessible(page);

  await openRoute(page, "/planner?a=%E6%9D%BE%E5%B1%B1%E6%B8%AC%E7%AB%99&b=%E6%9D%BE%E5%B1%B1%E6%B8%AC%E7%AB%99");
  await expect(page.getByTestId("same-location")).toBeVisible();
  await expect(page.getByRole("button", { name: "下載共同時段 CSV" })).toHaveCount(0);
});
