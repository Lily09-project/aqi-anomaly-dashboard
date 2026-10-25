import { readFile } from "node:fs/promises";
import { expect, expectAccessible, fetchJson, openRoute, test } from "./fixtures";

interface Overview {
  stations: { station: string; aqi: number; category_label: string }[];
}
interface WhatIf {
  parity_cases: { inputs: Record<string, number>; expected: number }[];
}

test.describe("F1 測站總覽地圖", () => {
  test("map and list show every station; clicking a station opens its detail", async ({ page }) => {
    await openRoute(page, "/");
    const overview = await fetchJson<Overview>(page, "overview.json");
    await expect(page.locator(".taiwan-map a")).toHaveCount(overview.stations.length);
    await expect(page.locator(".station-card")).toHaveCount(overview.stations.length);
    const worst = [...overview.stations].sort((a, b) => b.aqi - a.aqi)[0]!;
    await expect(page.locator(".station-card").first()).toContainText(worst.station);
    await expect(page.locator(".station-card").first()).toContainText(worst.category_label);
    await expect(page.getByTestId("data-badge")).toHaveText("測試資料");

    await page.locator(".taiwan-map a", { hasText: worst.station.replace("測站", "") }).click();
    await expect(page).toHaveURL(new RegExp(`#/station/${encodeURIComponent(worst.station)}`));
    await expect(page.locator("h1")).toHaveText(worst.station);
    await expect(page.getByTestId("advice")).not.toBeEmpty();
  });
});

test.describe("F2 機率預報與出門規劃", () => {
  test("planner settings live in the URL and the recommendation updates", async ({ page }) => {
    await openRoute(page, "/station/前金測站");
    await expect(page.getByTestId("forecast-table").locator("tbody tr")).toHaveCount(24);
    const first = await page.getByTestId("best-window").innerText();
    await page.getByRole("radio", { name: "一般民眾" }).check();
    await expect(page).toHaveURL(/for=general/);
    await page.getByLabel("活動時長").selectOption("6");
    await expect(page).toHaveURL(/hours=6/);
    await expect(page.getByTestId("planner-result")).toContainText("連續 6 小時");
    expect(await page.getByTestId("best-window").innerText()).not.toBe("");
    await page.reload();
    await expect(page.getByLabel("活動時長")).toHaveValue("6");
    await expect(page.getByRole("radio", { name: "一般民眾" })).toBeChecked();
    await page.getByLabel("切換測站").selectOption("松山測站");
    await expect(page.locator("h1")).toHaveText("松山測站");
    expect(first).toMatch(/\d+\/\d+ \d{2}:00–\d{2}:00/);
    await expectAccessible(page);
  });
});

test.describe("F3 污染傳播追蹤", () => {
  test("detected lags match the truth and the replay can be paused and stepped", async ({ page }) => {
    await openRoute(page, "/propagation");
    const agreement = (await page.getByTestId("lag-agreement").innerText()).split("/").map(Number);
    expect(agreement[0]).toBe(agreement[1]);
    await expect(page.getByTestId("isolated")).toContainText("宜蘭");
    await expect(page.getByTestId("isolated")).toContainText("花蓮");

    const time = page.getByTestId("replay-time");
    const start = await time.innerText();
    await page.getByRole("button", { name: "下一小時" }).click();
    await expect(page).toHaveURL(/frame=1/);
    expect(await time.innerText()).not.toBe(start);
    await page.getByRole("button", { name: "播放" }).click();
    await expect(page.getByRole("button", { name: "暫停" })).toHaveAttribute("aria-pressed", "true");
    await page.waitForTimeout(1000);
    await page.getByRole("button", { name: "暫停" }).click();
    const paused = await time.innerText();
    await page.waitForTimeout(800);
    expect(await time.innerText()).toBe(paused);
    await expectAccessible(page);
  });

  test("reduced motion slows playback and says so", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openRoute(page, "/propagation?frame=3");
    await expect(page.getByText("已偵測到「減少動態效果」設定")).toBeVisible();
    await expect(page.locator(".replay-slider input")).toHaveValue("3");
  });
});

test.describe("F4 異常歸因與相似事件", () => {
  test("filters, attribution ordering, similar events and CSV export", async ({ page }) => {
    await openRoute(page, "/anomalies");
    expect(Number((await page.getByTestId("recall").innerText()).replace("%", ""))).toBeGreaterThanOrEqual(80);
    await page.getByRole("radio", { name: "局部" }).check();
    await expect(page).toHaveURL(/kind=local/);
    const items = page.getByTestId("event-list").locator("a");
    expect(await items.count()).toBeGreaterThan(0);
    for (const text of await items.allInnerTexts()) expect(text).toContain("局部");

    const z = (await page.getByTestId("drivers-table").locator("tbody td:last-child").allInnerTexts()).map(Number);
    const sorted = [...z].sort((a, b) => Math.abs(b) - Math.abs(a));
    expect(z).toEqual(sorted);

    const title = await page.locator("#event-title").innerText();
    await page.getByTestId("similar-list").locator("a").first().click();
    await expect(page).toHaveURL(/id=/);
    await expect(page.locator("#event-title")).not.toHaveText(title);

    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: /下載 CSV/ }).click();
    const file = await download;
    const csv = await readFile((await file.path())!, "utf8");
    expect(csv.split("\r\n")[0]).toContain("station");
    await expectAccessible(page);
  });
});

test.describe("F5 情境模擬", () => {
  test("sliders recompute the prediction in the browser", async ({ page }) => {
    await openRoute(page, "/whatif");
    const prediction = page.getByTestId("whatif-prediction");
    const before = Number(await prediction.innerText());
    const slider = page.getByRole("slider", { name: "目前 AQI", exact: true });
    await slider.focus();
    for (let i = 0; i < 40; i += 1) await page.keyboard.press("ArrowRight");
    await expect(prediction).not.toHaveText(String(before));
    expect(Number(await prediction.innerText())).toBeGreaterThan(before);
    await page.getByLabel("從地點目前狀態載入").selectOption("前金測站");
    await expect(page.getByTestId("value-aqi_now")).not.toHaveText("55.7");
    await page.getByRole("button", { name: "重設為典型值" }).click();
    await expect(page.getByTestId("value-aqi_now")).toHaveText(/55\.7/);
    // The browser model is fed the same numbers the Python tests check.
    const model = await fetchJson<WhatIf>(page, "whatif.json");
    expect(model.parity_cases.length).toBeGreaterThanOrEqual(10);
    await expectAccessible(page);
  });
});

test.describe("F6 模型監控", () => {
  test("baselines, calibration and drift are reported", async ({ page }) => {
    await openRoute(page, "/model");
    await expect(page.getByTestId("beats-persistence")).toHaveText("24/24");
    await expect(page.getByTestId("mae-table").locator("tbody tr")).toHaveCount(24);
    await expect(page.getByTestId("coverage-table").locator("tbody tr")).toHaveCount(24);
    await expect(page.getByTestId("drift-table").locator("tbody tr")).toHaveCount(8);
    const coverage = Number((await page.getByTestId("mean-coverage").innerText()).replace("%", ""));
    expect(coverage).toBeGreaterThan(75);
  });
});

test.describe("F7 資料可信度", () => {
  test("every file passes in-browser SHA-256 verification against the manifest", async ({ page }) => {
    await openRoute(page, "/data");
    await expect(page.getByTestId("integrity-summary")).toHaveText("6/6");
    const manifest = await fetchJson<{ files: Record<string, string> }>(page, "manifest.json");
    const rows = page.getByTestId("integrity-table").locator("tbody tr");
    await expect(rows).toHaveCount(6);
    for (const [file, hash] of Object.entries(manifest.files)) {
      await expect(rows.filter({ hasText: file })).toContainText(hash);
      await expect(rows.filter({ hasText: file })).toContainText("相符");
    }
    await expect(page.getByTestId("truth-table").locator("tbody tr")).toHaveCount(6);
    await expect(page.getByTestId("data-source")).toHaveText("測試資料");
  });
});
