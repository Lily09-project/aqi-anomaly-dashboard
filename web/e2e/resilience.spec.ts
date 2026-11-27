import { expect, test } from "./fixtures";

// A tab opened before a redeploy asks for page chunks that no longer exist.
test("a missing page chunk explains the update instead of showing a browser error", async ({ page, watch }) => {
  await page.route(/assets\/Model-.*\.js/, (route) => route.fulfill({ status: 404, body: "not found" }));
  await page.goto("./");
  await expect(page.locator("main h1").first()).toBeVisible();
  await page.locator("nav a:visible", { hasText: "模型監控" }).first().click();
  const alert = page.getByRole("alert");
  await expect(alert).toContainText("網站剛更新過");
  await expect(alert).not.toContainText("dynamically imported");
  await expect(alert.getByRole("button", { name: "重新載入頁面" })).toBeVisible();
  // The 404 and the failed module import are the expected cause of this test, not site errors.
  watch.errors.length = 0;
});
