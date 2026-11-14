import { taiwanLocalTimestampMs } from "./format";
import type { QuantileHour } from "./types";

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

export function sharedWindows(a: readonly QuantileHour[], b: readonly QuantileHour[], hours: number, threshold: number, now: number) {
  if (!Number.isFinite(now) || !Number.isFinite(threshold) || threshold < 1 || !Number.isInteger(hours) || hours < 1) return [];
  const left = byHour(a, now);
  const right = byHour(b, now);
  const shared = [...left].flatMap(([time, first]) => {
    const second = right.get(time);
    return second ? [{ time, a: first, b: second }] : [];
  }).sort((x, y) => x.time - y.time);
  return shared.flatMap((_, start) => {
    const rows = shared.slice(start, start + hours);
    if (rows.length !== hours || !rows.every((row, offset) => row.time === rows[0]!.time + offset * 3_600_000)) return [];
    const highest = Math.max(...rows.flatMap((row) => [row.a.p50, row.b.p50]));
    if (highest > threshold) return [];
    const upper = Math.max(...rows.flatMap((row) => [row.a.p90, row.b.p90]));
    return [{ rows, highest, upper }];
  });
}
