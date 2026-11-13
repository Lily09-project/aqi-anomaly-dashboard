import { describe, expect, it } from "vitest";
import { axisTicks, placeLabels, textWidth } from "./chart-layout";

/** 72 hourly labels, "11/11 12:00" … "11/14 11:00", like the station forecast chart. */
const hourly = Array.from({ length: 72 }, (_, i) => {
  const h = (12 + i) % 24;
  const day = 11 + Math.floor((12 + i) / 24);
  return `11/${day} ${String(h).padStart(2, "0")}:00`;
});

const linear = (n: number, lo: number, hi: number) => (i: number) => lo + ((hi - lo) * i) / (n - 1);

function boxes(ticks: ReturnType<typeof axisTicks>, x: (i: number) => number) {
  return ticks.map((t) => {
    const w = textWidth(t.label, 12);
    const cx = x(t.i);
    const start = t.anchor === "start" ? cx : t.anchor === "end" ? cx - w : cx - w / 2;
    return [start, start + w] as const;
  });
}

describe("axisTicks", () => {
  it("never lets labels overlap or leave the chart at phone widths", () => {
    for (const width of [280, 300, 320, 343]) {
      const x = linear(hourly.length, 40, width - 12);
      const ticks = axisTicks(hourly, x, 0, width);
      expect(ticks.length).toBeGreaterThanOrEqual(2);
      const b = boxes(ticks, x);
      b.forEach(([s, e], k) => {
        expect(s).toBeGreaterThanOrEqual(-1);
        expect(e).toBeLessThanOrEqual(width + 1);
        if (k > 0) expect(s).toBeGreaterThan(b[k - 1]![1]);
      });
    }
  });

  it("uses short date labels at midnight on a phone", () => {
    const x = linear(hourly.length, 40, 331);
    expect(axisTicks(hourly, x, 0, 343).map((t) => t.label)).toEqual(["11/12", "11/13", "11/14"]);
  });

  it("adds clock ticks when the chart is wide, with the date on the first one", () => {
    const x = linear(hourly.length, 40, 868);
    const labels = axisTicks(hourly, x, 0, 880).map((t) => t.label);
    expect(labels[0]).toBe("11/11 12:00");
    expect(labels).toContain("11/12");
    expect(labels.length).toBeGreaterThan(3);
  });

  it("falls back to evenly spaced labels for non-time axes", () => {
    const labels = ["1h", "2h", "3h", "4h", "5h", "6h"];
    const ticks = axisTicks(labels, linear(6, 44, 300), 0, 312);
    expect(ticks[0]).toMatchObject({ i: 0, anchor: "middle" });
    expect(ticks.at(-1)?.i).toBe(5);
  });
});

describe("placeLabels", () => {
  it("separates labels of a dense cluster of points", () => {
    const points = [
      { x: 300, y: 40, label: "松山 44", r: 8 },
      { x: 292, y: 44, label: "板橋 53", r: 8 },
      { x: 280, y: 42, label: "桃園 54", r: 8 },
    ];
    const placed = placeLabels(points, { x: 0, y: 0, w: 600, h: 400 }, 14);
    const rects = placed.map((p, i) => {
      const w = textWidth(points[i]!.label, 14);
      const left = p.anchor === "start" ? p.x : p.anchor === "end" ? p.x - w : p.x - w / 2;
      return { left, right: left + w, top: p.y - 14, bottom: p.y };
    });
    for (let a = 0; a < rects.length; a++)
      for (let b = a + 1; b < rects.length; b++) {
        const A = rects[a]!;
        const B = rects[b]!;
        const overlap = A.left < B.right && B.left < A.right && A.top < B.bottom && B.top < A.bottom;
        expect(overlap).toBe(false);
      }
  });
});
