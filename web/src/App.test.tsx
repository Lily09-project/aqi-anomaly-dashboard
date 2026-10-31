import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import type { Loader } from "./lib/data";
import type { DataFiles, Overview, Propagation, Provenance, Station } from "./lib/types";

const CATEGORIES = [
  { upper: 50, key: "good", label: "良好" },
  { upper: 100, key: "moderate", label: "普通" },
  { upper: 500, key: "unhealthy", label: "不健康" },
];

const hour = (h: number) => `2026-10-21T${String(h).padStart(2, "0")}:00:00`;

function station(name: string, aqi: number, rise: number, coordinates: { latitude: number | null; longitude: number | null }): Station {
  return {
    station: name,
    county: "測試縣",
    ...coordinates,
    coordinate_source: "test",
    aqi,
    pm25: 10,
    pm10: 20,
    o3: 30,
    wind_speed: 2,
    category: "moderate",
    category_label: "普通",
    history: [],
    forecast: Array.from({ length: 12 }, (_, h) => ({ h: h + 1, t: hour(h), p10: aqi - 5, p50: aqi + rise * h, p90: aqi + 10 + rise * h })),
  };
}

function datasets(stations: Station[]): Partial<DataFiles> {
  const overview: Overview = { latest: "2026-10-20T23:00", stations, categories: CATEGORIES, planner_thresholds: { sensitive: 50, general: 100 } };
  const propagation: Propagation = {
    max_lag: 12,
    min_correlation: 0.3,
    links: [],
    nearest_upstream: {},
    matrix: {},
    episode: { start: hour(0), end: hour(5), times: Array.from({ length: 6 }, (_, h) => hour(h)), aqi: { [stations[0]!.station]: [50, 60, 70, 80, 90, 100] } },
    ground_truth: null,
  };
  const provenance = {
    data_source: "test",
    is_simulated: true,
    provider: null,
    seed: 1,
    range: { start: hour(0), end: hour(5) },
    stations: stations.length,
    rows: 1,
    completeness: 1,
    input_sha256: null,
    schema_sha256: null,
    injected_events_file: null,
    sources: [],
  } satisfies Provenance;
  return { "overview.json": overview, "propagation.json": propagation, "provenance.json": provenance };
}

function fakeLoader(files: Partial<DataFiles>): Loader {
  return {
    load: (name) => (name in files ? Promise.resolve(files[name]!) : Promise.reject(new Error(`missing ${name}`))),
    manifest: () => Promise.resolve({ schema_version: "2.0", files: {} }),
    verifiedFiles: () => [],
  } as Loader;
}

const TWO_STATIONS = [
  station("甲測站", 80, 0, { latitude: 25.05, longitude: 121.5 }),
  station("乙測站", 40, 5, { latitude: null, longitude: null }),
];

beforeEach(() => {
  window.scrollTo = vi.fn() as typeof window.scrollTo;
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  window.history.replaceState(null, "", "#/");
});

describe("home forecast outlook", () => {
  it("uses only forecast hours that have not started yet and tolerates unknown coordinates", async () => {
    // 03:30 Taiwan time: hours 00–03 have started, so the next six are 04–09.
    vi.useFakeTimers({ toFake: ["Date"], now: Date.parse("2026-10-21T03:30:00+08:00") });
    window.history.replaceState(null, "", "#/");
    render(<App loader={fakeLoader(datasets(TWO_STATIONS))} />);
    const rising = await screen.findByText("未來 6 小時預估上升最多");
    // 乙: median at 09:00 is 40 + 5 × 9 = 85, a rise of +45 over the current 40.
    expect(rising.closest("a")).toHaveTextContent("乙測站（+45）");
    expect(screen.getByRole("row", { name: /乙測站/ })).toHaveTextContent("—, —");
    expect(screen.queryByTestId("rising-insufficient")).toBeNull();
  });

  it("says when fewer than six future forecast hours remain", async () => {
    vi.useFakeTimers({ toFake: ["Date"], now: Date.parse("2026-10-21T07:30:00+08:00") });
    window.history.replaceState(null, "", "#/");
    render(<App loader={fakeLoader(datasets(TWO_STATIONS))} />);
    expect(await screen.findByTestId("rising-insufficient")).toHaveTextContent("未來預報不足 6 小時");
    expect(screen.getAllByText(/未來預報不足 6 小時/).length).toBeGreaterThan(1);
  });
});

describe("error boundary", () => {
  it("shows the error state inside the shell instead of unmounting the site", async () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const broken = { ...TWO_STATIONS[0]!, forecast: undefined } as unknown as Station;
    window.history.replaceState(null, "", "#/");
    render(<App loader={fakeLoader(datasets([broken]))} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("無法顯示這個頁面");
    expect(screen.getByRole("navigation", { name: "主要頁面" })).toBeInTheDocument();
  });
});

describe("propagation replay and the URL", () => {
  it("re-syncs from external URL changes and writes the frame only when playback stops", async () => {
    window.history.replaceState(null, "", "#/propagation?frame=2");
    render(<App loader={fakeLoader(datasets(TWO_STATIONS))} />);
    const slider = await screen.findByRole("slider");
    expect(slider).toHaveValue("2");

    act(() => {
      window.history.replaceState(null, "", "#/propagation");
      window.dispatchEvent(new HashChangeEvent("hashchange"));
    });
    expect(slider).toHaveValue("0");

    const replace = vi.spyOn(window.history, "replaceState");
    fireEvent.click(screen.getByRole("button", { name: "播放" }));
    await act(() => new Promise((resolve) => setTimeout(resolve, 1000)));
    expect(Number((slider as HTMLInputElement).value)).toBeGreaterThan(0);
    expect(replace).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "暫停" }));
    const paused = (slider as HTMLInputElement).value;
    expect(replace).toHaveBeenCalledTimes(1);
    expect(window.location.hash).toBe(`#/propagation?frame=${paused}`);
  });
});
