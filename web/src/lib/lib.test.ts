import { describe, expect, it, vi } from "vitest";
import { ADVICE, bestWindow, categoryOf, DEFAULT_CATEGORIES, defaultInputs, exceedanceProbability, futureForecast, predictWhatIf, whatIfContributions, windowRisks } from "./air";
import { coverageStatus, episodeFrame, eventRows, filterEvents, lagAgreement, peakFrames, skill, upstreamGain } from "./analysis";
import { escapeCell, toCsv } from "./csv";
import { createLoader, IntegrityError, sha256Hex } from "./data";
import whatifFixture from "./fixtures/whatif.json";
import { addHours, formatClock, formatDay, formatHour, formatNumber, formatPercent, formatSigned, taiwanLocalTimestampMs } from "./format";
import { makeProjection, outlinePath, TAIWAN_OUTLINE } from "./geo";
import { parseRoute, routeToHash, type Route } from "./router";
import type { AnomalyEvent, HorizonMetrics, Link, Propagation, WhatIf } from "./types";

const whatif = whatifFixture as WhatIf;

describe("AQI categories", () => {
  it("maps values onto the Ministry of Environment bands", () => {
    expect(categoryOf(0)?.key).toBe("good");
    expect(categoryOf(50)?.key).toBe("good");
    expect(categoryOf(50.1)?.key).toBe("moderate");
    expect(categoryOf(120)?.label).toBe("對敏感族群不健康");
    expect(categoryOf(999)?.key).toBe("hazardous");
    expect(categoryOf(null)).toBeNull();
    expect(categoryOf(Number.NaN)).toBeNull();
    expect(categoryOf(10, [])).toBeNull();
    for (const c of DEFAULT_CATEGORIES) expect(ADVICE[c.key]?.sensitive).toBeTruthy();
  });
});


describe("future forecast times", () => {
  const forecast = [
    { h: 1, t: "2026-10-26T11:00", p10: 10, p50: 20, p90: 30 },
    { h: 2, t: "2026-10-26T12:00", p10: 10, p50: 20, p90: 30 },
    { h: 3, t: "2026-10-26T13:00:00.250", p10: 10, p50: 20, p90: 30 },
  ];

  it("parses Taiwan-local timestamps independently of the viewer time zone", () => {
    expect(taiwanLocalTimestampMs("2026-10-26T12:00")).toBe(Date.parse("2026-10-26T04:00:00Z"));
    expect(taiwanLocalTimestampMs("2026-10-26T13:00:00.250")).toBe(Date.parse("2026-10-26T05:00:00.250Z"));
    expect(taiwanLocalTimestampMs("2026-02-30T12:00")).toBeNull();
    expect(taiwanLocalTimestampMs("2026-10-26T24:00")).toBeNull();
    expect(taiwanLocalTimestampMs("2026-10-26T12:00Z")).toBe(Date.parse("2026-10-26T12:00:00Z"));
  });

  it("honors the offset-bearing production forecast format and equivalent UTC instants", () => {
    const instant = Date.parse("2026-10-26T04:00:00Z");
    expect(taiwanLocalTimestampMs("2026-10-26T12:00:00+08:00")).toBe(instant);
    expect(taiwanLocalTimestampMs("2026-10-26T04:00:00Z")).toBe(instant);
    expect(taiwanLocalTimestampMs("2026-10-26T00:00:00-04:00")).toBe(instant);
    expect(taiwanLocalTimestampMs("2026-10-26T09:30:00+05:30")).toBe(instant);
    expect(taiwanLocalTimestampMs("2026-10-26T12:00:00.250+08:00")).toBe(instant + 250);
    for (const invalid of [
      "2026-02-30T12:00:00+08:00",
      "2026-10-26T12:00:00+24:00",
      "2026-10-26T12:00:00+08:60",
      "2026-10-26T12:00:00+0800",
      "2026-10-26T12:00:00Zjunk",
    ]) expect(taiwanLocalTimestampMs(invalid)).toBeNull();
    const production = [11, 12, 13].map((hour) => ({
      h: hour, t: `2026-10-26T${hour}:00:00+08:00`,
    }));
    expect(futureForecast(production, instant).map((hour) => hour.h)).toEqual([12, 13]);
    expect(futureForecast(production, instant + 1).map((hour) => hour.h)).toEqual([13]);
    expect(futureForecast(production, instant + 3_600_001)).toEqual([]);
  });

  it("excludes expired hours while including a forecast exactly at the evaluation time", () => {
    const now = Date.parse("2026-10-26T04:00:00Z");
    expect(futureForecast(forecast, now).map((hour) => hour.h)).toEqual([2, 3]);
    expect(futureForecast(forecast, now + 1).map((hour) => hour.h)).toEqual([3]);
    expect(futureForecast(forecast, Number.NaN)).toEqual([]);
  });
});

// The same cases as tests/test_analytics_core.py, so both planners agree.
const FORECAST = [
  { p10: 40, p50: 60, p90: 90 },
  { p10: 70, p50: 110, p90: 160 },
  { p10: 30, p50: 45, p90: 70 },
  { p10: 20, p50: 35, p90: 55 },
  { p10: 90, p50: 130, p90: 200 },
];

describe("outing planner (mirrors src/analytics/planner.py)", () => {
  it("reads exceedance probability off the piecewise CDF", () => {
    const hour = { p10: 40, p50: 60, p90: 100 };
    expect(exceedanceProbability(hour, 60)).toBeCloseTo(0.5, 12);
    expect(exceedanceProbability(hour, 40)).toBeCloseTo(0.9, 12);
    expect(exceedanceProbability(hour, 80)).toBeCloseTo(0.3, 12);
    expect(exceedanceProbability(hour, 140)).toBeCloseTo(0, 12);
    expect(exceedanceProbability(hour, 0)).toBeCloseTo(1, 12);
    expect(exceedanceProbability(hour, 38)).toBeCloseTo(1 - (0.1 - 0.02 * 2), 12);
    expect(exceedanceProbability(hour, 30)).toBeCloseTo(1, 12);
  });

  it("picks the lowest-risk window and rejects impossible lengths", () => {
    for (const hours of [1, 2, 3]) {
      const best = bestWindow(FORECAST, hours, 100);
      const risks = FORECAST.slice(0, FORECAST.length - hours + 1).map(
        (_, start) => FORECAST.slice(start, start + hours).reduce((s, h) => s + exceedanceProbability(h, 100), 0) / hours,
      );
      expect(best?.risk).toBeCloseTo(Math.min(...risks), 12);
    }
    expect(bestWindow(FORECAST, 1, 100)?.start).toBe(3);
    expect(bestWindow(FORECAST, 6, 150)).toBeNull();
    expect(bestWindow(FORECAST, 0, 150)).toBeNull();
    expect(windowRisks(FORECAST, 2, 100)).toHaveLength(4);
    expect(windowRisks(FORECAST, 9, 100)).toEqual([]);
  });

  it("breaks ties by cleaner air, then the earlier start", () => {
    const clean = [
      { p10: 10, p50: 20, p90: 30 },
      { p10: 5, p50: 15, p90: 25 },
      { p10: 5, p50: 15, p90: 25 },
    ];
    expect(bestWindow(clean, 1, 150)?.start).toBe(1);
  });
});

describe("what-if model", () => {
  it("matches every Python reference prediction within 1e-6", () => {
    expect(whatif.parity_cases.length).toBeGreaterThanOrEqual(10);
    for (const c of whatif.parity_cases) {
      expect(Math.abs(predictWhatIf(whatif, c.inputs) - c.expected)).toBeLessThan(1e-6);
    }
  });

  it("decomposes a prediction into per-input contributions", () => {
    const inputs = defaultInputs(whatif);
    expect(Object.keys(inputs)).toEqual(whatif.inputs.map((i) => i.key));
    const parts = whatIfContributions(whatif, inputs);
    expect(parts.map((p) => p.key)).toEqual([...whatif.feature_order.slice(0, -2), "hour"]);
    const total = parts.reduce((s, p) => s + p.value, whatif.intercept);
    expect(total).toBeCloseTo(predictWhatIf(whatif, inputs), 9);
    // Missing inputs fall back to zero rather than NaN.
    expect(Number.isFinite(predictWhatIf(whatif, {}))).toBe(true);
  });

  it("responds in the expected direction to the current AQI", () => {
    const base = defaultInputs(whatif);
    expect(predictWhatIf(whatif, { ...base, aqi_now: 120 })).toBeGreaterThan(predictWhatIf(whatif, { ...base, aqi_now: 40 }));
  });
});

const event = (overrides: Partial<AnomalyEvent>): AnomalyEvent => ({
  id: "x",
  station: "松山測站",
  start: "2026-09-01T00:00",
  end: "2026-09-01T03:00",
  peak: "2026-09-01T01:00",
  duration_hours: 4,
  peak_aqi: 120,
  peak_pm25: 50,
  kind: "local",
  drivers: [{ variable: "pm25", label: "PM2.5", z: 6 }],
  similar: [],
  context: [],
  ...overrides,
});

describe("analysis helpers", () => {
  it("filters and orders events newest first", () => {
    const events = [
      event({ id: "a", start: "2026-09-01T00:00" }),
      event({ id: "b", start: "2026-09-03T00:00", kind: "regional" }),
      event({ id: "c", start: "2026-09-02T00:00", station: "前金測站" }),
      event({ id: "d", start: "2026-09-02T00:00", station: "板橋測站" }),
    ];
    // Same start: stations follow zh-Hant collation.
    const tie = "前金測站".localeCompare("板橋測站", "zh-Hant") < 0 ? ["c", "d"] : ["d", "c"];
    expect(filterEvents(events, {}).map((e) => e.id)).toEqual(["b", ...tie, "a"]);
    expect(filterEvents(events, { kind: "local" }).map((e) => e.id)).toEqual([...tie, "a"]);
    expect(filterEvents(events, { station: "前金測站" }).map((e) => e.id)).toEqual(["c"]);
    const rows = eventRows([event({ kind: "regional", drivers: [] })]);
    expect(rows[0]).toMatchObject({ kind: "區域", top_driver: "" });
    expect(eventRows([event({})])[0]).toMatchObject({ kind: "局部", top_driver: "PM2.5" });
  });

  it("summarises forecast skill, upstream gain and calibration", () => {
    expect(skill(6, 8)).toBeCloseTo(0.25);
    expect(skill(6, 0)).toBe(0);
    const h = { downstream_mae: 9, downstream_mae_without_upstream: 10 } as HorizonMetrics;
    expect(upstreamGain(h)).toBeCloseTo(0.1);
    expect(upstreamGain({ ...h, downstream_mae: null })).toBeNull();
    expect(upstreamGain({ ...h, downstream_mae_without_upstream: 0 })).toBeNull();
    expect(coverageStatus(0.82, 0.8)).toBe("calibrated");
    expect(coverageStatus(0.7, 0.8)).toBe("too-narrow");
    expect(coverageStatus(0.95, 0.8)).toBe("too-wide");
  });

  it("checks detected lags against the injected truth", () => {
    const link = (lag: number, truth: number | null): Link => ({ upstream: "a", downstream: "b", lag_hours: lag, r: 0.7, r_synchronous: 0.6, truth_lag: truth });
    expect(lagAgreement([link(2, 2), link(5, 6), link(3, 8), link(1, null)])).toEqual({ matched: 2, total: 3 });
  });

  it("replays an episode frame by frame", () => {
    const episode: Propagation["episode"] = {
      start: "s",
      end: "e",
      times: ["t0", "t1", "t2"],
      aqi: { 松山測站: [90, 60, 40], 前金測站: [30, 50, 110], 花蓮測站: [null, null, null] },
    };
    expect(episodeFrame(episode, 1)).toEqual({ 松山測站: 60, 前金測站: 50, 花蓮測站: null });
    expect(episodeFrame(episode, 99)).toEqual({ 松山測站: 40, 前金測站: 110, 花蓮測站: null });
    expect(episodeFrame(episode, -3)["松山測站"]).toBe(90);
    expect(peakFrames(episode)).toEqual([
      { station: "松山測站", frame: 0, aqi: 90 },
      { station: "前金測站", frame: 2, aqi: 110 },
    ]);
  });
});

describe("geo", () => {
  it("projects Taiwan into the viewBox with a closed outline", () => {
    const projection = makeProjection(400);
    expect(projection.height).toBeGreaterThan(projection.width);
    for (const [lon, lat] of TAIWAN_OUTLINE) {
      const [x, y] = projection.project(lon, lat);
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(projection.width);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(projection.height);
    }
    // Taipei sits north-east of Kaohsiung.
    const [tx, ty] = projection.project(121.56, 25.05);
    const [kx, ky] = projection.project(120.29, 22.63);
    expect(tx).toBeGreaterThan(kx);
    expect(ty).toBeLessThan(ky);
    const path = outlinePath(projection);
    expect(path.startsWith("M")).toBe(true);
    expect(path.endsWith("Z")).toBe(true);
  });
});

describe("format", () => {
  it("formats numbers, percentages and Taiwan-local timestamps", () => {
    expect(formatNumber(12.345, 1)).toBe("12.3");
    expect(formatNumber(null)).toBe("—");
    expect(formatPercent(0.826, 1)).toBe("82.6%");
    expect(formatPercent(undefined)).toBe("—");
    expect(formatSigned(2.25)).toBe("+2.3");
    expect(formatSigned(-0.01)).toBe("0.0");
    expect(formatSigned(-1.5)).toBe("-1.5");
    expect(formatHour("2026-10-20T23:00")).toBe("10/20 23:00");
    expect(formatHour("2026-10-02T07:00:00")).toBe("10/2 07:00");
    expect(formatHour("bad")).toBe("bad");
    expect(formatDay("2026-10-20T23:00")).toBe("2026-10-20");
    expect(formatClock("2026-10-20T23:00")).toBe("23:00");
    expect(formatClock("x")).toBe("x");
    expect(addHours("2026-10-20T23:00", 1)).toBe("2026-10-21T00:00");
    expect(addHours("2026-12-31T22:00:00", 3)).toBe("2027-01-01T01:00");
    expect(addHours("nope", 1)).toBe("nope");
  });
});

describe("router", () => {
  it("round-trips every route and validates parameters", () => {
    const routes: Route[] = [
      { name: "home" },
      { name: "station", station: "前金測站", sensitivity: "general", hours: 3 },
      { name: "station", station: "松山測站" },
      { name: "propagation", frame: 12 },
      { name: "propagation" },
      { name: "anomalies", id: "板橋測站-2026082822", station: "板橋測站", kind: "local" },
      { name: "anomalies" },
      { name: "whatif" },
      { name: "model" },
      { name: "data" },
    ];
    for (const route of routes) expect(parseRoute(routeToHash(route))).toEqual(route);
    expect(parseRoute("")).toEqual({ name: "home" });
    expect(parseRoute("#/station")).toEqual({ name: "not-found", path: "/station" });
    expect(parseRoute("#/station/x?hours=99&for=all")).toEqual({ name: "station", station: "x", sensitivity: undefined, hours: undefined });
    expect(parseRoute("#/propagation?frame=-1")).toEqual({ name: "propagation", frame: undefined });
    expect(parseRoute("#/anomalies?kind=weird")).toMatchObject({ kind: undefined });
    expect(parseRoute("#/nope")).toEqual({ name: "not-found", path: "/nope" });
    expect(routeToHash({ name: "not-found", path: "/nope" })).toBe("#/nope");
  });
});

describe("csv", () => {
  it("neutralises spreadsheet formulas and quotes special characters", () => {
    for (const attack of ['=HYPERLINK("https://example.invalid")', "+SUM(1,2)", "-2+3", "@SUM(1,2)", "\t=1+1", " =1+1", "\n@SUM(1,2)"]) {
      expect(escapeCell(attack).replace(/^"/, "")).toMatch(/^'/);
    }
    expect(escapeCell(-3)).toBe("-3");
    expect(escapeCell('a,"b"')).toBe('"a,""b"""');
    expect(escapeCell(null)).toBe("");
    expect(escapeCell("前金測站")).toBe("前金測站");
    expect(toCsv(["station", "aqi"], [{ station: "前金測站", aqi: 113.4 }]).startsWith("﻿station,aqi\r\n前金測站,113.4")).toBe(true);
  });
});

describe("data loader", () => {
  const encoder = new TextEncoder();
  const respond = (body: string, status = 200) => new Response(encoder.encode(body), { status });

  it("verifies every file against the manifest and caches it", async () => {
    const body = '{"stations":[]}';
    const digest = await sha256Hex(encoder.encode(body).buffer as ArrayBuffer);
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith("manifest.json")) return respond(JSON.stringify({ schema_version: "2.0", files: { "overview.json": digest } }));
      if (url.endsWith("overview.json")) return respond(body);
      return respond("missing", 404);
    });
    const loader = createLoader("./", fetcher);
    await expect(loader.load("overview.json")).resolves.toEqual({ stations: [] });
    await loader.load("overview.json");
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(loader.verifiedFiles()).toEqual(["overview.json"]);
    await expect(loader.load("model.json")).rejects.toThrow("HTTP 404");
  });

  it("rejects tampered files", async () => {
    const fetcher = async (url: string) =>
      url.endsWith("manifest.json") ? respond(JSON.stringify({ schema_version: "2.0", files: { "model.json": "0".repeat(64) } })) : respond("{}");
    await expect(createLoader("./", fetcher).load("model.json")).rejects.toBeInstanceOf(IntegrityError);
  });

  it("retries the manifest after a transient failure", async () => {
    const body = "{}";
    const digest = await sha256Hex(encoder.encode(body).buffer as ArrayBuffer);
    let manifestCalls = 0;
    const fetcher = async (url: string) => {
      if (url.endsWith("manifest.json")) {
        manifestCalls += 1;
        return manifestCalls === 1 ? respond("down", 503) : respond(JSON.stringify({ schema_version: "2.0", files: { "model.json": digest } }));
      }
      return respond(body);
    };
    const loader = createLoader("./", fetcher);
    await expect(loader.load("model.json")).rejects.toThrow("HTTP 503");
    await expect(loader.load("model.json")).resolves.toEqual({});
    expect(manifestCalls).toBe(2);
  });

  it("refetches a stale manifest and file once, bypassing the cache, before reporting tampering", async () => {
    const oldBody = '{"v":1}';
    const newBody = '{"v":2}';
    const hash = async (text: string) => sha256Hex(encoder.encode(text).buffer as ArrayBuffer);
    const manifestFor = async (text: string) => JSON.stringify({ schema_version: "2.0", files: { "model.json": await hash(text) } });
    let deployed = oldBody;
    const calls: [string, RequestInit | undefined][] = [];
    const fetcher = async (url: string, init?: RequestInit) => {
      calls.push([url, init]);
      return url.endsWith("manifest.json") ? respond(await manifestFor(deployed)) : respond(deployed);
    };
    const loader = createLoader("./", fetcher);
    await loader.manifest();
    deployed = newBody; // the site is redeployed while the tab still holds the old manifest
    await expect(loader.load("model.json")).resolves.toEqual({ v: 2 });
    expect(calls.filter(([, init]) => init?.cache === "reload").map(([url]) => url).sort()).toEqual(["./data/manifest.json", "./data/model.json"]);
  });
});
