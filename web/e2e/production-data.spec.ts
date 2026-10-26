import { expect, expectAccessible, fetchJson, openRoute, test } from "./fixtures";
// Independent oracle: never reuse the application parser when checking production timestamps.
const forecastInstant = (value: string) => Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : `${value}+08:00`);

interface Provenance {
  provider: string;
  data_source: string;
  is_simulated: boolean;
  is_model_estimate: boolean;
  native_temporal_resolution_hours: number;
  api_output_temporal_resolution_hours: number;
  spatial_resolution_km: number;
  rows: number;
  stations: number;
  input_sha256: string;
}

interface Overview {
  stations: { station: string; forecast: { t: string }[] }[];
}

test.describe("正式公開空品模型資料", () => {
  test("the public site labels Open-Meteo/CAMS estimates and renders usable locations", async ({ page }) => {
    const provenance = await fetchJson<Provenance>(page, "provenance.json");
    const overview = await fetchJson<Overview>(page, "overview.json");

    expect(provenance.provider).toBe("open_meteo_cams_global");
    expect(provenance.data_source).toBe("Open-Meteo CAMS Global model estimates");
    expect(provenance.is_model_estimate).toBe(true);
    expect(provenance.is_simulated).toBe(false);
    expect(provenance.native_temporal_resolution_hours).toBe(3);
    expect(provenance.api_output_temporal_resolution_hours).toBe(1);
    expect(provenance.spatial_resolution_km).toBe(45);
    expect(provenance.rows).toBeGreaterThan(0);
    expect(provenance.stations).toBe(overview.stations.length);
    expect(provenance.input_sha256).toMatch(/^[a-f0-9]{64}$/);
    expect(overview.stations.length).toBeGreaterThan(0);

    const firstForecast = overview.stations[0]!.forecast[0]!;
    const evaluationTime = forecastInstant(firstForecast.t) + 30 * 60_000;
    expect(Number.isFinite(evaluationTime)).toBe(true);
    await page.clock.install({ time: evaluationTime });

    await openRoute(page, "/");
    await expect(page.getByTestId("data-badge")).toHaveText("CAMS 模型估算");
    await expect(page.locator(".taiwan-map a")).toHaveCount(overview.stations.length);
    await page.locator(".station-card").first().click();
    const stationName = await page.locator(".station-head h1").textContent();
    const selectedStation = overview.stations.find((station) => station.station === stationName);
    expect(selectedStation).toBeDefined();
    const forecastTable = page.getByTestId("forecast-table");
    const asOfMs = Number(await forecastTable.getAttribute("data-as-of-ms"));
    expect(Number.isFinite(asOfMs)).toBe(true);
    const displayedTimes = await forecastTable.locator("tbody tr[data-forecast-time]").evaluateAll((rows) =>
      rows.map((row) => row.getAttribute("data-forecast-time") ?? ""),
    );
    const expectedFutureTimes = selectedStation!.forecast
      .filter((hour) => {
        const timestamp = forecastInstant(hour.t);
        return Number.isFinite(timestamp) && timestamp >= asOfMs;
      })
      .map((hour) => hour.t);
    expect(asOfMs).toBe(evaluationTime);
    expect(expectedFutureTimes.length).toBeGreaterThanOrEqual(2);
    expect(displayedTimes).toEqual(expectedFutureTimes);
    expect(displayedTimes.length).toBeLessThanOrEqual(24);
    const bestWindow = page.getByTestId("best-window");
    await expect(bestWindow).toHaveCount(1);
    const bestStart = await bestWindow.getAttribute("data-window-start");
    expect(bestStart).toBeTruthy();
    expect(forecastInstant(bestStart!)).toBeGreaterThanOrEqual(asOfMs);

    const lastForecastMs = Math.max(...selectedStation!.forecast.map((hour) => forecastInstant(hour.t)));
    await page.clock.setFixedTime(lastForecastMs + 1);
    await page.reload();
    await expect(page.getByTestId("planner-result")).toContainText("不足");
    await expect(forecastTable.locator("tbody tr[data-forecast-time]")).toHaveCount(0);
    await expect(bestWindow).toHaveCount(0);
    await expectAccessible(page);

    await openRoute(page, "/data");
    await expect(page.getByTestId("data-source")).toHaveText("Open-Meteo · CAMS Global");
    await expect(page.getByTestId("integrity-summary")).toHaveText("6/6");
    await expect(page.getByText(/不是測站實測/)).toBeVisible();
    await expectAccessible(page);
  });
});
