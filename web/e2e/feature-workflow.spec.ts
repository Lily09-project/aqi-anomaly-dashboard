import { expect, openRoute, test } from "./fixtures";

test("兩地出門規劃 keeps settings after reload", async ({ page }) => {
  await openRoute(page, "/planner");
  await expect(page.getByRole("heading", { name: "兩地出門規劃" })).toBeVisible();
  await page.getByLabel("連續時數").selectOption("1");
  await page.getByLabel("AQI 門檻").selectOption("150");
  await expect(page).toHaveURL(/threshold=150/);
  await page.reload();
  await expect(page.getByLabel("AQI 門檻")).toHaveValue("150");
  const date = new Date("2030-01-01T00:00:00Z");
  await page.clock.setFixedTime(date);
  await page.reload();
  await expect(page.getByText(/共同預報時數不足|暫停提供共同時段/)).toBeVisible();
});
