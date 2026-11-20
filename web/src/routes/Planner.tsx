import { useState } from "react";
import { useDataset, useDocumentTitle, useNow, useRoute } from "../app/hooks";
import { Chapter, PageHead } from "../components/Chapter";
import { ChartFrame, Legend, MultiLine, type LegendItem, type Series } from "../components/charts";
import { DataTime, STALE_AFTER_HOURS, StaleNotice } from "../components/Freshness";
import { ScrollRegion } from "../components/ScrollRegion";
import { EmptyState, Gate } from "../components/States";
import { downloadText, toCsv } from "../lib/csv";
import { formatHour, formatNumber, formatSpan, hoursSince, taiwanLocalIso } from "../lib/format";
import type { Route } from "../lib/router";
import { sharedHours, sharedWindows, windowEnd, windowRuns, type SharedWindow } from "../lib/sharedWindows";
import type { Overview, Provenance } from "../lib/types";
import "./Planner.css";

type PlannerRoute = Extract<Route, { name: "planner" }>;

/** Windows listed before 「顯示全部」; the chart above already shows every one of them. */
const SHOWN_WINDOWS = 6;

const show = (value: number) => formatNumber(value, 1);
/** "11/20 15:00–17:00": the end is the moment the window is over. */
const spanOf = (window: SharedWindow) => formatSpan(taiwanLocalIso(window.rows[0]!.time), taiwanLocalIso(windowEnd(window)));

function PlannerView({ data, provenance, route }: { data: Overview; provenance: Provenance; route: PlannerRoute }) {
  const [, navigate] = useRoute();
  const now = useNow();
  const [showAll, setShowAll] = useState(false);
  const a = data.stations.find((station) => station.station === route.a) ?? data.stations[0];
  const b = data.stations.find((station) => station.station === route.b) ?? data.stations.find((station) => station !== a) ?? a;
  if (!a || !b) return <EmptyState title="沒有可比較的地點" />;
  const hours = route.hours ?? 2;
  const threshold = route.threshold ?? data.planner_thresholds.sensitive;
  const rule = route.conservative ? "區間上界（P90）也不超過門檻" : "點預測（P50）不超過門檻";
  // Control changes rewrite the current entry, so Back leaves the page instead of undoing one select at a time.
  const update = (patch: Partial<PlannerRoute>) =>
    navigate({ ...route, a: a.station, b: b.station, hours, threshold, ...patch }, { replace: true });
  // Picking the other side's location swaps the two, so A and B never end up the same.
  const pickA = (value: string) => update({ a: value, b: value === b.station ? a.station : b.station });
  const pickB = (value: string) => update({ b: value, a: value === a.station ? b.station : a.station });
  const same = a.station === b.station;
  const age = hoursSince(data.latest, now);
  const stale = provenance.is_model_estimate && age !== null && age >= STALE_AFTER_HOURS;
  const usable = !stale && !same;
  const timeline = usable ? sharedHours(a.forecast, b.forecast, now) : [];
  const windows = usable ? sharedWindows(a.forecast, b.forecast, hours, threshold, now, route.conservative) : [];
  const first = windows[0];
  const hasForecast = first !== undefined || (usable && sharedWindows(a.forecast, b.forecast, hours, Number.MAX_VALUE, now).length > 0);
  const runs = windowRuns(timeline, windows);
  const coveredHours = runs.reduce((sum, [start, end]) => sum + end - start + 1, 0);
  const listed = showAll ? windows : windows.slice(0, SHOWN_WINDOWS);
  const options = data.stations.map(({ station }) => <option key={station}>{station}</option>);

  const download = () => {
    const columns = ["start_utc", "end_utc", "location_a", "location_b", "threshold", "rule", "highest_p50", "highest_p90", "data_time_taipei", "source"];
    const rows = windows.map((window) => ({
      start_utc: new Date(window.rows[0]!.time).toISOString(),
      // Exclusive end: the moment the window is over, as shown on the page.
      end_utc: new Date(windowEnd(window)).toISOString(),
      location_a: a.station, location_b: b.station, threshold,
      rule: route.conservative ? "p90" : "p50", highest_p50: window.highest, highest_p90: window.upper,
      data_time_taipei: data.latest, source: provenance.data_source,
    }));
    downloadText("aqi-shared-windows.csv", toCsv(columns, rows), "text/csv;charset=utf-8");
  };

  const series: Series[] = [
    { key: "a50", label: `${a.station}（A）點預測 P50`, values: timeline.map((row) => row.a.p50), tone: 1 },
    { key: "b50", label: `${b.station}（B）點預測 P50`, values: timeline.map((row) => row.b.p50), tone: 2 },
    { key: "a90", label: `A 區間上界 P90`, values: timeline.map((row) => row.a.p90), tone: 3, thin: true },
    { key: "b90", label: `B 區間上界 P90`, values: timeline.map((row) => row.b.p90), tone: 4, thin: true },
  ];
  const legend: LegendItem[] = [
    ...series.map(({ key, label, tone, thin }) => ({ key, label, tone, thin })),
    { key: "threshold", label: `AQI 門檻 ${threshold}`, mark: "threshold" },
    ...(runs.length ? [{ key: "window", label: `符合條件的連續 ${hours} 小時時段`, mark: "window" as const }] : []),
  ];
  // Start the axis a little below the lowest median so close lines stay apart; never below 0.
  const lowest = Math.min(...timeline.flatMap((row) => [row.a.p50, row.b.p50]), threshold);
  const yFloor = Math.max(0, Math.floor((lowest - 15) / 10) * 10);
  const covered = new Set(windows.flatMap((window) => window.rows.map((row) => row.time)));

  return (
    <div className="stack">
      <section className="card planner-form" aria-label="時段條件">
        <label className="field">
          <span className="label">地點 A</span>
          <select className="input" value={a.station} onChange={(e) => pickA(e.target.value)}>{options}</select>
        </label>
        <label className="field">
          <span className="label">地點 B</span>
          <select className="input" value={b.station} onChange={(e) => pickB(e.target.value)}>{options}</select>
        </label>
        <label className="field">
          <span className="label">連續時數</span>
          <select className="input" value={hours} onChange={(e) => update({ hours: Number(e.target.value) })}>
            {Array.from({ length: 12 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1} 小時</option>)}
          </select>
        </label>
        <label className="field">
          <span className="label">AQI 門檻</span>
          <select className="input" value={threshold} onChange={(e) => update({ threshold: Number(e.target.value) })}>
            {[...new Set([threshold, 50, 75, 100, 150, data.planner_thresholds.sensitive, data.planner_thresholds.general])].sort((x, y) => x - y).map((value) => <option key={value}>{value}</option>)}
          </select>
        </label>
        <label className="field">
          <span className="label">判讀條件</span>
          <select className="input" value={route.conservative ? "upper" : "point"} onChange={(e) => update({ conservative: e.target.value === "upper" })}>
            <option value="point">點預測符合門檻</option>
            <option value="upper">區間上界也符合門檻</option>
          </select>
        </label>
        <p className="muted small planner-meta">
          <DataTime latest={data.latest} nowMs={now} /> · 台北時間{provenance.is_model_estimate && " · CAMS 模型網格估算"} · 時段結束時間為該時段結束的時刻
        </p>
      </section>

      {provenance.is_model_estimate && <StaleNotice latest={data.latest} nowMs={now} />}

      {same ? (
        <p className="notice" role="status" data-testid="same-location">
          地點 A 與地點 B 都是「{a.station}」。請改選另一個地點，才能比較兩地的共同時段。
        </p>
      ) : stale ? (
        <EmptyState title="目前暫停提供共同時段"><p>最近發布的預報已過期，請稍後再試。</p></EmptyState>
      ) : first ? (
        <Chapter
          no="01"
          title="最早符合門檻的時段"
          testId="first-shared-window"
          liveTakeaway
          takeaway={
            <>
              最早是 <strong data-testid="first-window">{spanOf(first)}</strong>：兩地最高點預測 {show(first.highest)}，預測區間上界最高 {show(first.upper)}
              {first.upper > threshold ? `，上界超過門檻 ${threshold}` : `，上界也不超過門檻 ${threshold}`}。
            </>
          }
          howTo={
            <p>
              「點預測符合門檻」只看兩地每小時的 P50；「區間上界也符合門檻」連 P90 都要不超過門檻，比較保守，符合的時段通常較少。80% 預測區間仍有預測誤差，只採用尚未開始的時段。
            </p>
          }
        >
          <details className="card planner-hours">
            <summary>查看最早時段的逐時預測</summary>
            <ScrollRegion label="最早時段的逐時預測">
              <table>
                <caption>逐時 AQI 點預測（P50）與 80% 預測區間（P10–P90），台北時間</caption>
                <thead><tr><th scope="col">時間</th><th scope="col">{a.station}（A）</th><th scope="col">{b.station}（B）</th></tr></thead>
                <tbody>{first.rows.map(({ time, a: left, b: right }) => (
                  <tr key={time}>
                    <th scope="row">{formatHour(taiwanLocalIso(time))}</th>
                    <td className="num">{show(left.p50)}（{show(left.p10)}–{show(left.p90)}）</td>
                    <td className="num">{show(right.p50)}（{show(right.p10)}–{show(right.p90)}）</td>
                  </tr>
                ))}</tbody>
              </table>
            </ScrollRegion>
          </details>
        </Chapter>
      ) : hasForecast ? (
        <EmptyState title="沒有符合門檻的共同時段"><p>可縮短時數、調整門檻或選擇其他地點；下方圖表標出兩地逐時預報與門檻。</p></EmptyState>
      ) : (
        <EmptyState title="兩地共同預報時數不足"><p>可縮短時數或選擇其他地點。</p></EmptyState>
      )}

      {timeline.length > 0 && (
        <Chapter
          no={first ? "02" : "01"}
          title="兩地逐時預報與符合的時段"
          liveTakeaway
          takeaway={
            windows.length ? (
              <span data-testid="planner-summary">
                接下來 {timeline.length} 個共同預報小時中，有 <strong>{windows.length}</strong> 個連續 {hours} 小時的時段符合「{rule}」，合計涵蓋 {coveredHours} 小時（綠色區塊）。
              </span>
            ) : (
              <span data-testid="planner-summary">
                接下來 {timeline.length} 個共同預報小時中，沒有連續 {hours} 小時能符合「{rule}」。
              </span>
            )
          }
        >
          <ChartFrame
            title={`${a.station} 與 ${b.station} 的逐時 AQI 預報（P50 與 P90）`}
            summary={`實線與虛線是兩地的點預測 P50，細線是區間上界 P90；紅色虛線是門檻 ${threshold}${runs.length ? `，綠色區塊是符合條件的時段，共 ${windows.length} 個` : "，沒有符合條件的時段"}。`}
            legend={<Legend series={legend} />}
            table={
              <table data-testid="planner-hourly-table">
                <thead>
                  <tr>
                    <th scope="col">時間</th>
                    <th scope="col">{a.station}（A）P50（P10–P90）</th>
                    <th scope="col">{b.station}（B）P50（P10–P90）</th>
                    <th scope="col">在符合的時段內</th>
                  </tr>
                </thead>
                <tbody>
                  {timeline.map(({ time, a: left, b: right }) => (
                    <tr key={time}>
                      <th scope="row">{formatHour(taiwanLocalIso(time))}</th>
                      <td className="num">{show(left.p50)}（{show(left.p10)}–{show(left.p90)}）</td>
                      <td className="num">{show(right.p50)}（{show(right.p10)}–{show(right.p90)}）</td>
                      <td>{covered.has(time) ? "是" : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
          >
            <MultiLine
              series={series}
              labels={timeline.map(({ time }) => formatHour(taiwanLocalIso(time)))}
              windows={runs}
              reference={{ value: threshold, label: `門檻 ${threshold}` }}
              yMin={yFloor}
              height={260}
              format={(v) => String(v)}
            />
          </ChartFrame>

          {windows.length > 0 && (
            <div className="planner-windows">
              <div className="planner-windows-head">
                <h3>符合條件的時段（{windows.length}）</h3>
                <button className="btn" type="button" onClick={download}>下載共同時段 CSV</button>
              </div>
              <ScrollRegion label="符合條件的時段">
                <table data-testid="planner-windows-table">
                  <thead>
                    <tr>
                      <th scope="col">時段</th>
                      <th scope="col" className="num">最高 P50</th>
                      <th scope="col" className="num">最高 P90</th>
                      <th scope="col">區間上界</th>
                    </tr>
                  </thead>
                  <tbody>
                    {listed.map((window) => (
                      <tr key={window.rows[0]!.time}>
                        <th scope="row">{spanOf(window)}</th>
                        <td className="num">{show(window.highest)}</td>
                        <td className="num">{show(window.upper)}</td>
                        <td>
                          {window.upper > threshold
                            ? <span className="tag" data-tone="warn">超過門檻</span>
                            : <span className="tag" data-tone="good">不超過門檻</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollRegion>
              {windows.length > SHOWN_WINDOWS && (
                <button className="btn planner-more" type="button" aria-expanded={showAll} onClick={() => setShowAll((value) => !value)}>
                  {showAll ? `只顯示前 ${SHOWN_WINDOWS} 個` : `顯示全部 ${windows.length} 個時段`}
                </button>
              )}
            </div>
          )}
        </Chapter>
      )}

      <details className="card">
        <summary>資料與判讀方式</summary>
        <p>一般條件檢查兩地每小時的點預測。較嚴格的條件也檢查預測區間上界，仍有預測誤差。時段寫成「開始–結束」，結束是該時段結束的時刻（例如 15:00–17:00 是 15 點與 16 點這兩個小時）；CSV 的 end_utc 也採同一規則。</p>
        <p>{a.station} · {a.coordinate_source}<br />{b.station} · {b.coordinate_source}</p>
      </details>
    </div>
  );
}

export default function Planner({ route }: { route: PlannerRoute }) {
  useDocumentTitle("兩地出門規劃");
  const data = useDataset("overview.json");
  const provenance = useDataset("provenance.json");
  return (
    <div className="page stack">
      <PageHead kicker="出門規劃 · 兩地共同時段" title="兩地出門規劃">
        <p className="lede">選兩個地點與活動時數，找出兩地預報都不超過 AQI 門檻的共同時段；改用預測區間上界判讀會更保守。</p>
      </PageHead>
      <Gate<[Overview, Provenance]> states={[data, provenance]}>
        {(overview, source) => <PlannerView data={overview} provenance={source} route={route} />}
      </Gate>
    </div>
  );
}
