/**
 * Layout helpers for the SVG charts: width-aware axis ticks and
 * collision-free map labels. Pure functions so they can be unit tested.
 */

/** Rough rendered width of a label: CJK glyphs are about 1em, digits and Latin about 0.6em. */
export function textWidth(text: string, size = 12): number {
  let width = 0;
  for (const ch of text) width += /[⺀-鿿豈-﫿＀-￯]/.test(ch) ? size : ch === " " ? size * 0.32 : size * 0.6;
  return width;
}

export interface Tick {
  i: number;
  label: string;
  anchor: "start" | "middle" | "end";
}

/** "11/13 08:00" style labels, as produced by formatHour. */
const TIME_LABEL = /^(\d{1,2}\/\d{1,2}) (\d{2}):(\d{2})$/;
const STRIDES = [1, 2, 3, 6, 12, 24, 48, 72, 168];
/** Minimum white space between two tick labels, in px. */
const TICK_GAP = 12;

/** Anchor each label so it stays inside [lo, hi]; null when neighbours would collide. */
function fit(candidates: { i: number; label: string }[], x: (i: number) => number, lo: number, hi: number, size: number): Tick[] | null {
  const ticks: Tick[] = [];
  let lastRight = -Infinity;
  for (const c of candidates) {
    const w = textWidth(c.label, size);
    const cx = x(c.i);
    let anchor: Tick["anchor"] = "middle";
    let start = cx - w / 2;
    if (start < lo) {
      anchor = "start";
      start = cx;
    } else if (cx + w / 2 > hi) {
      anchor = "end";
      start = cx - w;
    }
    if (start < lo - 1 || start + w > hi + 1 || start < lastRight + TICK_GAP) return null;
    lastRight = start + w;
    ticks.push({ i: c.i, label: c.label, anchor });
  }
  return ticks;
}

/**
 * Pick as many evenly spaced ticks as fit the chart's real width. Hourly time
 * labels snap to round clock hours (midnight shows the date, other ticks only
 * the time, the first tick both), so a phone gets "11/12 · 11/13 · 11/14"
 * instead of four overlapping "11/12 12:00" stamps.
 */
export function axisTicks(labels: string[], x: (i: number) => number, lo: number, hi: number, { size = 12, maxTicks = 6 } = {}): Tick[] {
  const n = labels.length;
  if (n === 0) return [];
  const parsed = labels.map((l) => TIME_LABEL.exec(l));
  if (n > 2 && parsed.every(Boolean)) {
    for (const stride of STRIDES) {
      const picks = parsed.flatMap((m, i) => {
        const [, day, hh, mm] = m as RegExpExecArray;
        const hour = Number(hh);
        if (mm !== "00" || (stride >= 24 ? hour !== 0 : hour % stride !== 0)) return [];
        return [{ i, label: hour === 0 ? (day as string) : `${hh}:00`, day: day as string }];
      });
      if (picks.length < 2 || picks.length > maxTicks) continue;
      // The first tick carries its date unless it already is one.
      const first = picks[0]!;
      if (!first.label.includes("/")) first.label = `${first.day} ${first.label}`;
      const ticks = fit(picks, x, lo, hi, size);
      if (ticks) return ticks;
    }
  }
  for (let count = Math.min(maxTicks, n); count >= 2; count--) {
    const indexes = Array.from({ length: count }, (_, k) => Math.round((k * (n - 1)) / (count - 1))).filter((v, k, a) => a.indexOf(v) === k);
    const ticks = fit(indexes.map((i) => ({ i, label: labels[i] ?? "" })), x, lo, hi, size);
    if (ticks) return ticks;
  }
  return fit([{ i: 0, label: labels[0] ?? "" }], x, lo, hi, size) ?? [];
}

export interface LabelBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PlacedLabel {
  /** Text anchor position. */
  x: number;
  y: number;
  anchor: "start" | "middle" | "end";
}

const overlaps = (a: LabelBox, b: LabelBox) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

/**
 * Greedy label placement for map points: try right, left, then the diagonals and
 * above/below; keep the first spot that clears every dot, every earlier label
 * and the frame. Points are handled north to south so the dense northern cluster
 * gets first pick. Falls back to the least-overlapping spot.
 */
export function placeLabels(
  points: { x: number; y: number; label: string; r: number }[],
  frame: LabelBox,
  size: number,
): PlacedLabel[] {
  const h = size * 1.15;
  const order = points.map((_, i) => i).sort((a, b) => (points[a]?.y ?? 0) - (points[b]?.y ?? 0));
  const dots: LabelBox[] = points.map((p) => ({ x: p.x - p.r, y: p.y - p.r, w: 2 * p.r, h: 2 * p.r }));
  const taken: LabelBox[] = [];
  const result: PlacedLabel[] = new Array(points.length);
  for (const index of order) {
    const p = points[index]!;
    const w = textWidth(p.label, size);
    const gap = p.r + 4;
    const candidates: [number, number, PlacedLabel["anchor"]][] = [
      [gap, 0, "start"],
      [-gap, 0, "end"],
      [gap * 0.7, -gap * 0.9, "start"],
      [gap * 0.7, gap * 0.9, "start"],
      [-gap * 0.7, -gap * 0.9, "end"],
      [-gap * 0.7, gap * 0.9, "end"],
      [0, -gap - h / 2, "middle"],
      [0, gap + h / 2, "middle"],
      [gap, -h, "start"],
      [gap, h, "start"],
      [-gap, -h, "end"],
      [-gap, h, "end"],
    ];
    let best: { box: LabelBox; placed: PlacedLabel; cost: number } | null = null;
    for (const [dx, dy, anchor] of candidates) {
      const ax = p.x + dx;
      const left = anchor === "start" ? ax : anchor === "end" ? ax - w : ax - w / 2;
      const box = { x: left - 2, y: p.y + dy - h / 2 - 1, w: w + 4, h: h + 2 };
      const outside = box.x < frame.x || box.y < frame.y || box.x + box.w > frame.x + frame.w || box.y + box.h > frame.y + frame.h;
      const cost = (outside ? 100 : 0) + taken.filter((t) => overlaps(t, box)).length * 10 + dots.filter((d, k) => k !== index && overlaps(d, box)).length * 10;
      if (!best || cost < best.cost) best = { box, placed: { x: ax, y: p.y + dy + size * 0.36, anchor }, cost };
      if (cost === 0) break;
    }
    taken.push(best!.box);
    result[index] = best!.placed;
  }
  return result;
}
