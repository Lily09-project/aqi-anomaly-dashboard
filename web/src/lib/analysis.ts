/** Small, pure helpers the pages use to summarise the exported analysis. */
import type { AnomalyEvent, HorizonMetrics, Link, Propagation } from "./types";

export interface EventFilter {
  station?: string;
  kind?: "local" | "regional";
}

export function filterEvents(events: readonly AnomalyEvent[], filter: EventFilter): AnomalyEvent[] {
  return events
    .filter((e) => (!filter.station || e.station === filter.station) && (!filter.kind || e.kind === filter.kind))
    .sort((a, b) => (a.start < b.start ? 1 : a.start > b.start ? -1 : a.station.localeCompare(b.station, "zh-Hant")));
}

export function eventRows(events: readonly AnomalyEvent[]): Record<string, unknown>[] {
  return events.map((e) => ({
    id: e.id,
    station: e.station,
    kind: e.kind === "local" ? "局部" : "區域",
    start: e.start,
    end: e.end,
    duration_hours: e.duration_hours,
    peak_aqi: e.peak_aqi,
    peak_pm25: e.peak_pm25,
    top_driver: e.drivers[0]?.label ?? "",
  }));
}

/** Forecast skill relative to a baseline: 1 − MAE / baseline MAE (higher is better). */
export function skill(mae: number, baselineMae: number): number {
  return baselineMae > 0 ? 1 - mae / baselineMae : 0;
}

/** Relative MAE reduction the upstream feature gives downstream stations at one horizon. */
export function upstreamGain(h: HorizonMetrics): number | null {
  if (h.downstream_mae === null || h.downstream_mae_without_upstream === null || h.downstream_mae_without_upstream <= 0) return null;
  return (h.downstream_mae_without_upstream - h.downstream_mae) / h.downstream_mae_without_upstream;
}

export type CoverageStatus = "calibrated" | "too-narrow" | "too-wide";

/**
 * Under-coverage is the costly failure (a band that is too confident), so the
 * lower tolerance is tighter than the upper one.
 */
export function coverageStatus(coverage: number, target: number, below = 0.05, above = 0.1): CoverageStatus {
  if (coverage < target - below) return "too-narrow";
  if (coverage > target + above) return "too-wide";
  return "calibrated";
}

/** How many detected lags land within ±1 h of the injected ground truth. */
export function lagAgreement(links: readonly Link[]): { matched: number; total: number } {
  const known = links.filter((l) => l.truth_lag !== null);
  return { matched: known.filter((l) => Math.abs(l.lag_hours - (l.truth_lag ?? 0)) <= 1).length, total: known.length };
}

/** AQI of every station at one frame of the replayed episode. */
export function episodeFrame(episode: Propagation["episode"], frame: number): Record<string, number | null> {
  const index = Math.min(Math.max(Math.round(frame), 0), Math.max(episode.times.length - 1, 0));
  return Object.fromEntries(Object.entries(episode.aqi).map(([station, values]) => [station, values[index] ?? null]));
}

/** The frame at which each station peaks during the episode (arrival order of the plume). */
export function peakFrames(episode: Propagation["episode"]): { station: string; frame: number; aqi: number }[] {
  const peaks: { station: string; frame: number; aqi: number }[] = [];
  for (const [station, values] of Object.entries(episode.aqi)) {
    let best = -1;
    values.forEach((v, i) => {
      if (v !== null && (best < 0 || v > (values[best] ?? -Infinity))) best = i;
    });
    if (best >= 0) peaks.push({ station, frame: best, aqi: values[best] ?? 0 });
  }
  return peaks.sort((a, b) => a.frame - b.frame || a.station.localeCompare(b.station, "zh-Hant"));
}
