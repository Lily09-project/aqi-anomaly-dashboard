import { taiwanLocalTimestampMs } from "./format";
import type { QuantileHour } from "./types";

const HOUR_MS = 3_600_000;

export interface SharedHour {
  /** Start of the hour, epoch ms. */
  time: number;
  a: QuantileHour;
  b: QuantileHour;
}

export interface SharedWindow {
  rows: SharedHour[];
  /** Highest point forecast (P50) of either location in the window. */
  highest: number;
  /** Highest upper bound (P90) of either location in the window. */
  upper: number;
}

function byHour(forecast: readonly QuantileHour[], now: number) {
  const result = new Map<number, QuantileHour>();
  for (const hour of forecast) {
    const time = taiwanLocalTimestampMs(hour.t);
    if (time === null || time < now || ![hour.p10, hour.p50, hour.p90].every(Number.isFinite)) continue;
    if (hour.p10 < 0 || hour.p10 > hour.p50 || hour.p50 > hour.p90) continue;
    result.set(time, hour);
  }
  return result;
}

/** Forecast hours both locations share that have not started yet, oldest first. */
export function sharedHours(a: readonly QuantileHour[], b: readonly QuantileHour[], now: number): SharedHour[] {
  if (!Number.isFinite(now)) return [];
  const left = byHour(a, now);
  const right = byHour(b, now);
  return [...left]
    .flatMap(([time, first]) => {
      const second = right.get(time);
      return second ? [{ time, a: first, b: second }] : [];
    })
    .sort((x, y) => x.time - y.time);
}

export function sharedWindows(a: readonly QuantileHour[], b: readonly QuantileHour[], hours: number, threshold: number, now: number, conservative = false): SharedWindow[] {
  if (!Number.isFinite(now) || !Number.isFinite(threshold) || threshold < 1 || !Number.isInteger(hours) || hours < 1) return [];
  const shared = sharedHours(a, b, now);
  return shared.flatMap((_, start) => {
    const rows = shared.slice(start, start + hours);
    if (rows.length !== hours || !rows.every((row, offset) => row.time === rows[0]!.time + offset * HOUR_MS)) return [];
    const highest = Math.max(...rows.flatMap((row) => [row.a.p50, row.b.p50]));
    if (highest > threshold) return [];
    const upper = Math.max(...rows.flatMap((row) => [row.a.p90, row.b.p90]));
    if (conservative && upper > threshold) return [];
    return [{ rows, highest, upper }];
  });
}

/** Exclusive end of a window: the moment its last hour is over. */
export function windowEnd(window: SharedWindow): number {
  return window.rows.at(-1)!.time + HOUR_MS;
}

/**
 * Overlapping windows merged into runs of hours, as [first, last] indexes into
 * `hours`, so a chart can shade every hour that belongs to some qualifying window.
 */
export function windowRuns(hours: readonly SharedHour[], windows: readonly SharedWindow[]): [number, number][] {
  const covered = new Set(windows.flatMap((w) => w.rows.map((row) => row.time)));
  const runs: [number, number][] = [];
  hours.forEach((hour, index) => {
    if (!covered.has(hour.time)) return;
    const last = runs.at(-1);
    const previous = hours[index - 1];
    if (last && last[1] === index - 1 && previous && hour.time - previous.time === HOUR_MS) last[1] = index;
    else runs.push([index, index]);
  });
  return runs;
}
