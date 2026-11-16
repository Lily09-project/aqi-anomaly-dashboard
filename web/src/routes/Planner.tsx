import { useDataset, useDocumentTitle, useNow, useRoute } from "../app/hooks";
import { DataTime, STALE_AFTER_HOURS, StaleNotice } from "../components/Freshness";
import { EmptyState, Gate } from "../components/States";
import { downloadText, toCsv } from "../lib/csv";
import { formatNumber, hoursSince } from "../lib/format";
import type { Route } from "../lib/router";
import { sharedWindows } from "../lib/sharedWindows";
import type { Overview, Provenance } from "../lib/types";

const taipeiTime = new Intl.DateTimeFormat("zh-TW", {
  timeZone: "Asia/Taipei", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});

type PlannerRoute = Extract<Route, { name: "planner" }>;

function PlannerView({ data, provenance, route }: { data: Overview; provenance: Provenance; route: PlannerRoute }) {
  const [, navigate] = useRoute();
  const now = useNow();
  const a = data.stations.find((station) => station.station === route.a) ?? data.stations[0];
  const b = data.stations.find((station) => station.station === route.b) ?? data.stations.find((station) => station !== a) ?? a;
  if (!a || !b) return <EmptyState title="沒有可比較的地點" />;
  const hours = route.hours ?? 2;
  const threshold = route.threshold ?? data.planner_thresholds.sensitive;
  const update = (patch: Partial<PlannerRoute>) => navigate({ ...route, a: a.station, b: b.station, hours, threshold, ...patch });
  const age = hoursSince(data.latest, now);
  const stale = provenance.is_model_estimate && age !== null && age >= STALE_AFTER_HOURS;
  const windows = stale ? [] : sharedWindows(a.forecast, b.forecast, hours, threshold, now, route.conservative);
  const first = windows[0];
  const hasForecast = first !== undefined || (!stale && sharedWindows(a.forecast, b.forecast, hours, Number.MAX_VALUE, now).length > 0);
  const timeRange = (rows: NonNullable<typeof first>["rows"]) =>
    `${taipeiTime.format(rows[0]!.time)} 至 ${taipeiTime.format(rows.at(-1)!.time + 3_600_000)}`;
  const options = data.stations.map(({ station }) => <option key={station}>{station}</option>);
  const show = (value: number) => formatNumber(value, 1);
  const download = () => {
    const columns = ["start_utc", "end_utc", "location_a", "location_b", "threshold", "rule", "highest_p50", "highest_p90", "data_time_taipei", "source"];
    const rows = windows.map(({ rows, highest, upper }) => ({
      start_utc: new Date(rows[0]!.time).toISOString(),
      end_utc: new Date(rows.at(-1)!.time + 3_600_000).toISOString(),
      location_a: a.station, location_b: b.station, threshold,
      rule: route.conservative ? "p90" : "p50", highest_p50: highest, highest_p90: upper,
      data_time_taipei: data.latest, source: provenance.data_source,
    }));
    downloadText("aqi-shared-windows.csv", toCsv(columns, rows), "text/csv;charset=utf-8");
  };
  return (
    <div className="stack">
      <section className="card controls-row" aria-label="時段條件">
        <label className="field">地點 A<select className="input" value={a.station} onChange={(e) => update({ a: e.target.value })}>{options}</select></label>
        <label className="field">地點 B<select className="input" value={b.station} onChange={(e) => update({ b: e.target.value })}>{options}</select></label>
        <label className="field">連續時數<select className="input" value={hours} onChange={(e) => update({ hours: Number(e.target.value) })}>
          {Array.from({ length: 12 }, (_, i) => <option key={i + 1} value={i + 1}>{i + 1} 小時</option>)}
        </select></label>
        <label className="field">AQI 門檻<select className="input" value={threshold} onChange={(e) => update({ threshold: Number(e.target.value) })}>
          {[...new Set([threshold, 50, 75, 100, 150, data.planner_thresholds.sensitive, data.planner_thresholds.general])].sort((x, y) => x - y).map((value) => <option key={value}>{value}</option>)}
        </select></label>
        <label className="field">判讀條件<select className="input" value={route.conservative ? "upper" : "point"}
          onChange={(e) => update({ conservative: e.target.value === "upper" })}>
          <option value="point">點預測符合門檻</option>
          <option value="upper">區間上界也符合門檻</option>
        </select></label>
      </section>
      <p className="muted"><DataTime latest={data.latest} nowMs={now} /> · 台北時間{provenance.is_model_estimate && " · CAMS 模型網格估算"}</p>
      {provenance.is_model_estimate && <StaleNotice latest={data.latest} nowMs={now} />}
      {first ? (
        <section aria-label="共同時段" className="stack">
          <div className="card stack" data-testid="first-shared-window">
            <h2>最早符合門檻的時段</h2>
            <strong>{timeRange(first.rows)}</strong>
            <p>兩地最高點預測 {show(first.highest)} · 預測區間上界最高 {show(first.upper)}
              {first.upper > threshold && "（超過門檻）"}</p>
          </div>
          <div><button className="btn" type="button" onClick={download}>下載共同時段 CSV</button></div>
          {windows.map(({ rows, highest, upper }, index) => (
            <details className="card" key={rows[0]!.time}>
              <summary>{index === 0 ? "查看最早時段的逐時預測" : `${timeRange(rows)} · 最高點預測 ${show(highest)}${upper > threshold ? " · 區間上界超過門檻" : ""}`}</summary>
              <div className="scroll-x"><table>
                <caption>逐時 AQI 點預測與 80% 預測區間（台北時間）</caption>
                <thead><tr><th scope="col">時間</th><th scope="col">{a.station}（A）</th><th scope="col">{b.station}（B）</th></tr></thead>
                <tbody>{rows.map(({ time, a: left, b: right }) => <tr key={time}>
                  <th scope="row">{taipeiTime.format(time)}</th><td>{show(left.p50)}（{show(left.p10)}–{show(left.p90)}）</td><td>{show(right.p50)}（{show(right.p10)}–{show(right.p90)}）</td>
                </tr>)}</tbody>
              </table></div>
            </details>
          ))}
        </section>
      ) : stale ? <EmptyState title="目前暫停提供共同時段"><p>最近發布的預報已過期，請稍後再試。</p></EmptyState>
        : hasForecast ? <EmptyState title="沒有符合門檻的共同時段"><p>可縮短時數、調整門檻或選擇其他地點。</p></EmptyState>
          : <EmptyState title="兩地共同預報時數不足"><p>可縮短時數或選擇其他地點。</p></EmptyState>}
      <details className="card">
        <summary>資料與判讀方式</summary>
        <p>一般條件檢查兩地每小時的點預測。較嚴格的條件也檢查預測區間上界，仍有預測誤差。</p>
        <p>{a.station} · {a.coordinate_source}<br />{b.station} · {b.coordinate_source}</p>
      </details>
    </div>
  );
}

export default function Planner({ route }: { route: PlannerRoute }) {
  useDocumentTitle("兩地出門規劃");
  const data = useDataset("overview.json");
  const provenance = useDataset("provenance.json");
  return <div className="page stack"><h1>兩地出門規劃</h1><Gate<[Overview, Provenance]> states={[data, provenance]}>
    {(overview, source) => <PlannerView data={overview} provenance={source} route={route} />}
  </Gate></div>;
}
