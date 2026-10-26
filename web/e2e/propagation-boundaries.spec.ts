import { createHash } from "node:crypto";
import { expect, expectAccessible, openRoute, test } from "./fixtures";

test("an unavailable episode has no active playback controls or fabricated times", async ({ page }) => {
  const text = JSON.stringify({
    max_lag: 12, min_correlation: 0.3, links: [], nearest_upstream: {}, matrix: {},
    episode: { start: null, end: null, times: [], aqi: {} }, ground_truth: null,
  });
  const digest = createHash("sha256").update(text).digest("hex");
  await page.route("**/data/propagation.json", (route) => route.fulfill({
    status: 200, contentType: "application/json", body: text,
  }));
  await page.route("**/data/manifest.json", async (route) => {
    const response = await route.fetch();
    const manifest = await response.json();
    manifest.files["propagation.json"] = digest;
    await route.fulfill({ response, json: manifest });
  });
  await openRoute(page, "/propagation");
  await expect(page.getByText("目前沒有可回放的時序區段")).toBeVisible();
  await expect(page.getByRole("button", { name: "播放", exact: true })).toHaveCount(0);
  await expect(page.getByRole("slider")).toHaveCount(0);
  await expect(page.getByText(/Invalid Date|NaN/)).toHaveCount(0);
  await expectAccessible(page);
});
