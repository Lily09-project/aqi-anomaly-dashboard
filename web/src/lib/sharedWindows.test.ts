import { expect, it } from "vitest";
import { sharedWindows } from "./sharedWindows";

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
