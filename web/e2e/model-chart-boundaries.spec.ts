import { createHash } from "node:crypto";
import { expect, fetchJson, openRoute, test } from "./fixtures";
import type { Model, Manifest } from "../src/lib/types";

test("low interval coverage stays visible inside the monitoring chart", async ({ page }) => {
  const model = await fetchJson<Model>(page, "model.json");
  const manifest = await fetchJson<Manifest>(page, "manifest.json");
  // Coverage below 60% is a legitimate monitoring result, not invalid data.
  model.horizons.forEach(h => { h.coverage = 0.4; });
  const body = JSON.stringify(model);
  manifest.files["model.json"] = createHash("sha256").update(body).digest("hex");
  await page.route("**/data/model.json", route => route.fulfill({ contentType: "application/json", body }));
  await page.route("**/data/manifest.json", route => route.fulfill({ json: manifest }));
  await openRoute(page, "/model");
  await expect(page.getByTestId("mean-coverage")).toHaveText("40.0%");
  const chart = page.getByRole("figure", { name: "80% 預測區間的實際覆蓋率", exact: true }).locator("svg.multi-line");
  await expect(chart).toBeVisible();
  const extent = await chart.locator("path.series").evaluate(node => {
    const bounds = (node as SVGGraphicsElement).getBBox();
    const svg = (node as SVGGraphicsElement).ownerSVGElement!;
    return { top: bounds.y, bottom: bounds.y + bounds.height, plotBottom: svg.viewBox.baseVal.height - 26 };
  });
  expect(extent.top).toBeGreaterThanOrEqual(10);
  expect(extent.bottom).toBeLessThanOrEqual(extent.plotBottom + 0.01);
});
