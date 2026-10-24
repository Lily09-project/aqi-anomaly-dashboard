import { scaleLinear } from "d3-scale";
import { area, line } from "d3-shape";
import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import { makeProjection, outlinePath } from "../lib/geo";
import "./charts.css";
import { ScrollRegion } from "./ScrollRegion";

/** Fallback width before the container has been measured (and in tests). */
const W = 520;

/**
 * Measure the chart's container so the viewBox matches real pixels: text stays
 * 13px on a wide desktop card and on a phone instead of scaling with the card.
 */
function useChartWidth(): [RefObject<HTMLDivElement | null>, number] {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(W);
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const next = Math.round(entry?.contentRect.width ?? 0);
      if (next > 0) setWidth(Math.min(Math.max(next, 280), 1200));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

/** Every chart pairs its SVG with an equivalent table for screen readers. */
export function ChartFrame({
  title,
  summary,
  table,
  interactive = false,
  children,
}: {
  title: string;
  summary: string;
  table: ReactNode;
  /** Interactive charts contain links, so they are a labelled group rather than one image. */
  interactive?: boolean;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <figure className="chart-frame" aria-labelledby={`${id}-title`}>
      <figcaption id={`${id}-title`} className="chart-title">
        {title}
      </figcaption>
      <div role={interactive ? "group" : "img"} aria-label={`${title}：${summary}`}>
        {children}
      </div>
      <details className="data-table">
        <summary>以表格檢視資料</summary>
        <ScrollRegion label={`${title}（資料表）`}>{table}</ScrollRegion>
      </details>
    </figure>
  );
}

export interface MapStation {
  name: string;
  lon: number;
  lat: number;
  /** Category key, used for the fill colour; null draws an empty marker. */
  category: string | null;
  label: string;
  emphasis?: boolean;
}

export interface MapLink {
  from: string;
  to: string;
  label: string;
}

/** Hand-placed labels for the dense northern cluster; others follow the coast. */
const LABEL_PLACEMENT: Record<string, [number, number, "start" | "end"]> = {
  松山測站: [13, -9, "start"],
  板橋測站: [12, 17, "start"],
  桃園測站: [-12, -9, "end"],
};

const MAP_WIDTH = 380;
const MAP_PAD = 76;

export function TaiwanMap({
  stations,
  links = [],
  hrefFor,
}: {
  stations: MapStation[];
  links?: MapLink[];
  /** When given, every station becomes a keyboard-reachable link. */
  hrefFor?: (station: string) => string;
}) {
  const projection = makeProjection(MAP_WIDTH);
  const markerId = useId().replace(/:/g, "");
  const position = new Map(stations.map((s) => [s.name, projection.project(s.lon, s.lat)]));
  return (
    <svg
      className="chart taiwan-map"
      viewBox={`${-MAP_PAD} -8 ${MAP_WIDTH + 2 * MAP_PAD} ${projection.height + 16}`}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden={hrefFor ? undefined : "true"}
    >
      <defs>
        <marker id={`arrow-${markerId}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" className="map-arrow-head" />
        </marker>
      </defs>
      <path className="map-land" d={outlinePath(projection)} aria-hidden="true" />
      {links.map((link) => {
        const a = position.get(link.from);
        const b = position.get(link.to);
        if (!a || !b) return null;
        const [x1, y1] = a;
        const [x2, y2] = b;
        const length = Math.hypot(x2 - x1, y2 - y1) || 1;
        // Stop short of the marker and bow the arrow so parallel links stay readable.
        const ux = (x2 - x1) / length;
        const uy = (y2 - y1) / length;
        const sx = x1 + ux * 10;
        const sy = y1 + uy * 10;
        const ex = x2 - ux * 11;
        const ey = y2 - uy * 11;
        const cx = (sx + ex) / 2 - uy * length * 0.18;
        const cy = (sy + ey) / 2 + ux * length * 0.18;
        return (
          <g key={`${link.from}-${link.to}`} className="map-link" aria-hidden="true">
            <path d={`M${sx},${sy} Q${cx},${cy} ${ex},${ey}`} markerEnd={`url(#arrow-${markerId})`} />
            <text x={cx} y={cy} textAnchor="middle" className="map-link-label">
              {link.label}
            </text>
          </g>
        );
      })}
      {stations.map((s) => {
        const [x, y] = position.get(s.name) ?? [0, 0];
        const [dx, dy, anchor] = LABEL_PLACEMENT[s.name] ?? (s.lon < 121 ? [-12, 4, "end"] : [12, 4, "start"]);
        const marker = (
          <>
            <circle cx={x} cy={y} r={s.emphasis ? 9 : 7} className="map-dot" data-category={s.category ?? "none"} />
            {/* An invisible larger target keeps touch hits ≥ 24px. */}
            <circle cx={x} cy={y} r={13} className="map-hit" />
            <text x={x + dx} y={y + dy} textAnchor={anchor} className="map-label">
              {s.label}
            </text>
          </>
        );
        const className = s.emphasis ? "map-station is-emphasis" : "map-station";
        return hrefFor ? (
          <a key={s.name} href={hrefFor(s.name)} className={className} aria-label={`${s.name}：${s.label}`}>
            {marker}
          </a>
        ) : (
          <g key={s.name} className={className}>
            {marker}
          </g>
        );
      })}
    </svg>
  );
}

export interface BandPoint {
  label: string;
  p10: number;
  p50: number;
  p90: number;
}

/** Observed history followed by the P10–P90 forecast band, with a threshold and a highlighted window. */
export function ForecastBand({
  history,
  forecast,
  threshold,
  window,
  height = 240,
}: {
  history: { label: string; value: number | null }[];
  forecast: BandPoint[];
  threshold?: number;
  window?: { start: number; hours: number } | null;
  height?: number;
}) {
  const [box, width] = useChartWidth();
  const left = 40;
  const right = width - 12;
  const total = history.length + forecast.length;
  const values = [
    ...history.flatMap((h) => (h.value === null ? [] : [h.value])),
    ...forecast.flatMap((f) => [f.p10, f.p90]),
    ...(threshold === undefined ? [] : [threshold]),
  ];
  const max = Math.max(...values, 60);
  const x = scaleLinear().domain([0, Math.max(total - 1, 1)]).range([left, right]);
  const y = scaleLinear().domain([0, max * 1.08]).range([height - 26, 10]).nice();
  const historyPath = line<{ value: number | null }>()
    .defined((d) => d.value !== null)
    .x((_, i) => x(i))
    .y((d) => y(d.value ?? 0))(history);
  const offset = history.length;
  const bandPath = area<BandPoint>()
    .x((_, i) => x(offset + i))
    .y0((d) => y(d.p10))
    .y1((d) => y(d.p90))(forecast);
  const medianPath = line<BandPoint>()
    .x((_, i) => x(offset + i))
    .y((d) => y(d.p50))(forecast);
  const ticks = [0, Math.floor(offset / 2), offset, total - 1].filter((v, i, a) => a.indexOf(v) === i);
  const labelAt = (i: number) => (i < offset ? history[i]?.label : forecast[i - offset]?.label) ?? "";
  return (
    <div ref={box} className="chart-box">
      <svg className="chart forecast-band" viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
        {y.ticks(4).map((t) => (
          <g key={t}>
            <line className="grid-line" x1={left} x2={right} y1={y(t)} y2={y(t)} />
            <text x={left - 6} y={y(t) + 4} textAnchor="end">
              {t}
            </text>
          </g>
        ))}
        {window && (
          <rect
            className="best-window"
            x={x(offset + window.start) - 4}
            width={Math.max(x(offset + window.start + window.hours - 1) - x(offset + window.start) + 8, 8)}
            y={10}
            height={height - 36}
            rx={4}
          />
        )}
        <line className="now-line" x1={x(offset - 0.5)} x2={x(offset - 0.5)} y1={6} y2={height - 26} />
        <text x={x(offset - 0.5) + 4} y={18} className="now-label">
          預報開始
        </text>
        {threshold !== undefined && (
          <g>
            <line className="threshold-line" x1={left} x2={right} y1={y(threshold)} y2={y(threshold)} />
            <text x={right} y={y(threshold) - 5} textAnchor="end" className="threshold-label">
              門檻 {threshold}
            </text>
          </g>
        )}
        <path className="band" d={bandPath ?? ""} />
        <path className="history-line" d={historyPath ?? ""} />
        <path className="median-line" d={medianPath ?? ""} />
        {ticks.map((i) => (
          <text key={i} x={x(i)} y={height - 8} textAnchor={i === 0 ? "start" : i === total - 1 ? "end" : "middle"}>
            {labelAt(i)}
          </text>
        ))}
      </svg>
    </div>
  );
}

export interface Series {
  key: string;
  label: string;
  values: (number | null)[];
  /** 1–4 picks the colour and dash pattern, so series never rely on colour alone. */
  tone: 1 | 2 | 3 | 4;
}

export function MultiLine({
  series,
  labels,
  format = (v) => String(v),
  marker,
  span,
  reference,
  height = 220,
  yMin,
}: {
  series: Series[];
  labels: string[];
  format?: (v: number) => string;
  marker?: number;
  span?: [number, number];
  reference?: { value: number; label: string };
  height?: number;
  yMin?: number;
}) {
  const [box, width] = useChartWidth();
  const left = 44;
  const right = width - 12;
  const values = series.flatMap((s) => s.values.filter((v): v is number => v !== null));
  if (reference) values.push(reference.value);
  const lo = yMin ?? Math.min(...values, 0);
  const hi = Math.max(...values, lo + 1);
  const x = scaleLinear().domain([0, Math.max(labels.length - 1, 1)]).range([left, right]);
  const y = scaleLinear().domain([lo, hi + (hi - lo) * 0.08]).range([height - 26, 10]).nice();
  const ticks = [0, Math.floor((labels.length - 1) / 2), labels.length - 1].filter((v, i, a) => a.indexOf(v) === i);
  return (
    <div ref={box} className="chart-box">
      <svg className="chart multi-line" viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
        {y.ticks(4).map((t) => (
          <g key={t}>
            <line className="grid-line" x1={left} x2={right} y1={y(t)} y2={y(t)} />
            <text x={left - 6} y={y(t) + 4} textAnchor="end">
              {format(t)}
            </text>
          </g>
        ))}
        {span && <rect className="span" x={x(span[0])} width={Math.max(x(span[1]) - x(span[0]), 3)} y={10} height={height - 36} rx={3} />}
        {reference && (
          <g>
            <line className="threshold-line" x1={left} x2={right} y1={y(reference.value)} y2={y(reference.value)} />
            <text x={right} y={y(reference.value) - 5} textAnchor="end" className="threshold-label">
              {reference.label}
            </text>
          </g>
        )}
        {series.map((s) => (
          <path
            key={s.key}
            className={`series series-${s.tone}`}
            d={
              line<number | null>()
                .defined((v) => v !== null)
                .x((_, i) => x(i))
                .y((v) => y(v ?? 0))(s.values) ?? ""
            }
          />
        ))}
        {marker !== undefined && <line className="now-line" x1={x(marker)} x2={x(marker)} y1={6} y2={height - 26} />}
        {ticks.map((i) => (
          <text key={i} x={x(i)} y={height - 8} textAnchor={i === 0 ? "start" : i === labels.length - 1 ? "end" : "middle"}>
            {labels[i]}
          </text>
        ))}
      </svg>
    </div>
  );
}

export function Legend({ series }: { series: Pick<Series, "key" | "label" | "tone">[] }) {
  return (
    <ul className="legend">
      {series.map((s) => (
        <li key={s.key}>
          <svg width="28" height="10" aria-hidden="true">
            <line x1="1" x2="27" y1="5" y2="5" className={`series series-${s.tone}`} />
          </svg>
          {s.label}
        </li>
      ))}
    </ul>
  );
}

/**
 * One strip per station, ordered from upwind to downwind. A plume shows up as
 * a ridge that moves right row by row; the cursor marks the replay frame.
 */
export function ArrivalStrips({
  rows,
  labels,
  frame,
  rowHeight = 34,
}: {
  rows: { key: string; label: string; values: (number | null)[]; peak: number | null }[];
  labels: string[];
  frame: number;
  rowHeight?: number;
}) {
  const [box, width] = useChartWidth();
  const left = 92;
  const right = width - 12;
  const all = rows.flatMap((r) => r.values.filter((v): v is number => v !== null));
  const max = Math.max(...all, 1);
  const x = scaleLinear().domain([0, Math.max(labels.length - 1, 1)]).range([left, right]);
  const height = rows.length * rowHeight + 24;
  return (
    <div ref={box} className="chart-box">
      <svg className="chart arrival-strips" viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
        {rows.map((r, row) => {
          const base = (row + 1) * rowHeight;
          const y = scaleLinear().domain([0, max]).range([base, base - rowHeight * 0.92]);
          const path = area<number | null>()
            .defined((v) => v !== null)
            .x((_, i) => x(i))
            .y0(base)
            .y1((v) => y(v ?? 0))(r.values);
          return (
            <g key={r.key}>
              <line className="grid-line" x1={left} x2={right} y1={base} y2={base} />
              <path className="strip" d={path ?? ""} />
              <path className="strip-edge" d={line<number | null>().defined((v) => v !== null).x((_, i) => x(i)).y((v) => y(v ?? 0))(r.values) ?? ""} />
              {r.peak !== null && <circle className="strip-peak" cx={x(r.peak)} cy={y(r.values[r.peak] ?? 0)} r={3.5} />}
              <text x={left - 8} y={base - 6} textAnchor="end" className="row-label">
                {r.label}
              </text>
            </g>
          );
        })}
        <line className="now-line" x1={x(frame)} x2={x(frame)} y1={4} y2={height - 22} />
        <text x={left} y={height - 6}>
          {labels[0]}
        </text>
        <text x={right} y={height - 6} textAnchor="end">
          {labels.at(-1)}
        </text>
      </svg>
    </div>
  );
}

export function DivergingBars({
  rows,
  format,
  height = 30,
}: {
  rows: { key: string; label: string; value: number }[];
  format: (v: number) => string;
  height?: number;
}) {
  const [box, width] = useChartWidth();
  const labelWidth = 104;
  const extent = Math.max(...rows.map((r) => Math.abs(r.value)), 1);
  const x = scaleLinear().domain([-extent, extent]).range([labelWidth + 44, width - 48]);
  const total = rows.length * height + 8;
  return (
    <div ref={box} className="chart-box">
      <svg className="chart diverging" viewBox={`0 0 ${width} ${total}`} aria-hidden="true">
        <line className="zero" x1={x(0)} x2={x(0)} y1={0} y2={total} />
        {rows.map((r, i) => {
          const y = i * height + 4;
          const start = Math.min(x(0), x(r.value));
          return (
            <g key={r.key}>
              <text x={0} y={y + height / 2} className="row-label">
                {r.label}
              </text>
              <rect className={r.value >= 0 ? "pos" : "neg"} x={start} y={y + 4} width={Math.abs(x(r.value) - x(0))} height={height - 12} rx={3} />
              <text x={r.value >= 0 ? x(r.value) + 6 : x(r.value) - 6} y={y + height / 2} textAnchor={r.value >= 0 ? "start" : "end"} className="value-label">
                {format(r.value)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
