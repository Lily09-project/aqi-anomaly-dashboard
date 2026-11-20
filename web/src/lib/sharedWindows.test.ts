import { expect, it } from "vitest";
import { sharedHours, sharedWindows, windowEnd, windowRuns } from "./sharedWindows";

const hour = (t: string, p50 = 35) => ({ h: 1, t, p10: 10, p50, p90: 65 });
const a = [hour("2026-11-14T23:00:00+08:00"), hour("2026-11-15T00:00:00+08:00"), hour("2026-11-15T02:00:00+08:00")];
const now = Date.parse(a[0]!.t);
it("aligns equivalent instants across midnight and reports an upper bound above the threshold", () => {
  const b = [hour("2026-11-14T15:00:00Z"), hour("2026-11-14T16:00:00Z")];
  expect(sharedWindows(a, b, 2, 50, now).map((x) => [x.rows.length, x.highest, x.upper])).toEqual([[2, 35, 65]]);
  expect(sharedWindows(a, b, 2, 50, now + 1)).toEqual([]);
});
it("rejects gaps, absent intersections and points above the threshold", () => {
  expect(sharedWindows(a, [a[0]!, a[2]!], 2, 50, now)).toEqual([]);
  expect(sharedWindows(a, [], 1, 50, now)).toEqual([]);
  expect(sharedWindows(a, a, 1, 30, now)).toEqual([]);
  expect(sharedWindows(a, a, 1, 35, now)).toHaveLength(3);
});

it("requires both upper bounds to meet the threshold when requested", () => {
  expect(sharedWindows(a, a, 2, 50, now, true)).toEqual([]);
  expect(sharedWindows(a, a, 2, 65, now, true)).toHaveLength(1);
});

it("lists the shared future hours and merges overlapping windows into shaded runs", () => {
  const day = [0, 1, 2, 3, 4, 5].map((h) => hour(`2026-11-15T0${h}:00:00+08:00`, h === 3 ? 60 : 35));
  const start = Date.parse(day[0]!.t);
  const hours = sharedHours(day, day, start);
  expect(hours).toHaveLength(6);
  const windows = sharedWindows(day, day, 2, 50, start);
  // 00–02 and 01–03 overlap; 03:00 is above the threshold; 04–06 stands alone.
  expect(windows.map((w) => w.rows[0]!.time)).toEqual([0, 1, 4].map((h) => start + h * 3_600_000));
  expect(windowRuns(hours, windows)).toEqual([[0, 2], [4, 5]]);
  expect(windowEnd(windows[0]!)).toBe(start + 2 * 3_600_000);
  expect(windowRuns(hours, [])).toEqual([]);
  expect(sharedHours(day, day, Number.NaN)).toEqual([]);
});
