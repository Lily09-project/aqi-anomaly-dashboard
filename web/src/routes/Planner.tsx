import { useDataset, useDocumentTitle, useNow, useRoute } from "../app/hooks";
import { EmptyState, Gate } from "../components/States";
import { addHours, formatHour, formatNumber } from "../lib/format";
import type { Route } from "../lib/router";
import { sharedWindows } from "../lib/sharedWindows";
import type { Overview, Provenance } from "../lib/types";

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
  const windows = sharedWindows(a.forecast, b.forecast, hours, threshold, now);
  const options = data.stations.map(({ station }) => <option key={station}>{station}</option>);
  const show = (value: number) => formatNumber(value, 1);
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
      </section>
      <p className="muted">資料時點 {formatHour(data.latest)}（台北時間）。{provenance.is_model_estimate ? "使用 CAMS 模型網格估算。" : "資料來源依本站資料契約。"}排名依開始時間，兩地逐時點預測都須低於或等於門檻。區間上界仍可能超過門檻。</p>
      <p className="muted">{a.station}：{a.coordinate_source}。{b.station}：{b.coordinate_source}。</p>
      {windows.length === 0 ? <EmptyState title="沒有符合條件的共同時段"><p>請調整時數、門檻或地點。</p></EmptyState> : (
        <section aria-label="共同時段" className="stack">
          <h2>{windows.length} 個共同時段</h2>
          {windows.map(({ rows, highest, upper }) => (
            <details className="card" key={rows[0]!.time}>
              <summary>{formatHour(rows[0]!.a.t)} 至 {formatHour(addHours(rows.at(-1)!.a.t, 1))} · 最高點預測 {show(highest)}
                {upper > threshold ? " · 區間上界超過門檻" : ""}</summary>
              <div className="scroll-x"><table>
                <thead><tr><th scope="col">時間</th><th scope="col">{a.station}（A）</th><th scope="col">{b.station}（B）</th></tr></thead>
                <tbody>{rows.map(({ time, a: first, b: second }) => <tr key={time}>
                  <th scope="row">{formatHour(first.t)}</th><td>{show(first.p50)}（{show(first.p10)}–{show(first.p90)}）</td><td>{show(second.p50)}（{show(second.p10)}–{show(second.p90)}）</td>
                </tr>)}</tbody>
              </table></div>
            </details>
          ))}
        </section>
      )}
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
