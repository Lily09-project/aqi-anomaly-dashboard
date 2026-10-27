import { useDataset, useDocumentTitle, useRoute } from "../app/hooks";
import { ChartFrame, DivergingBars, Legend, MultiLine, type Series } from "../components/charts";
import { ScrollRegion } from "../components/ScrollRegion";
import { EmptyState, Gate } from "../components/States";
import { eventRows, filterEvents } from "../lib/analysis";
import { downloadText, toCsv } from "../lib/csv";
import { formatHour, formatNumber, formatPercent, formatSigned } from "../lib/format";
import { routeToHash } from "../lib/router";
import type { Anomalies, AnomalyEvent } from "../lib/types";
import "./Anomalies.css";

type Kind = "local" | "regional";
const KIND_LABEL: Record<Kind, string> = { local: "局部", regional: "區域" };

interface Props {
  id?: string;
  station?: string;
  kind?: Kind;
}

function EventDetail({ event, all, filter, windowHours }: { event: AnomalyEvent; all: Map<string, AnomalyEvent>; filter: Props; windowHours: number }) {
  const startIndex = event.context.findIndex((c) => c.t >= event.start);
  const endIndex = event.context.findIndex((c) => c.t > event.end);
  const span: [number, number] = [Math.max(startIndex, 0), endIndex < 0 ? event.context.length - 1 : Math.max(endIndex - 1, 0)];
  const series: Series[] = [
    { key: "pm25", label: "PM2.5 資料", values: event.context.map((c) => c.pm25), tone: 1 },
    { key: "baseline", label: "同地點同時段的典型值（中位數）", values: event.context.map((c) => c.baseline), tone: 4 },
  ];
  const top = event.drivers[0];
  return (
    <article className="card event-detail" aria-labelledby="event-title" data-testid="event-detail">
      <header>
        <span className="eyebrow">
          {formatHour(event.start)}–{formatHour(event.end)} · {event.duration_hours} 小時
        </span>
        <h2 id="event-title">
          {event.station}{" "}
          <span className="tag" data-tone={event.kind === "local" ? "warn" : "info"}>
            {KIND_LABEL[event.kind]}事件
          </span>
        </h2>
        <p className="muted">
          {event.kind === "local"
            ? `其他地點在高峰前後 ${windowHours} 小時內沒有異常高峰，呈現單一地點高峰；僅憑模型資料無法判斷排放來源。`
            : `其他地點在高峰前後 ${windowHours} 小時內（最大時序落後窗口）也出現異常高峰，呈現多個地點同步高峰；不能據此判定污染來源。`}
          高峰 AQI {formatNumber(event.peak_aqi)}、PM2.5 {formatNumber(event.peak_pm25, 1)} µg/m³（{formatHour(event.peak)}）。
        </p>
      </header>

      <ChartFrame
        title="事件期間各因子的偏離程度"
        summary={event.drivers.map((d) => `${d.label} z=${formatSigned(d.z, 1)}`).join("、")}
        table={
          <table data-testid="drivers-table">
            <thead>
              <tr>
                <th scope="col">排名</th>
                <th scope="col">因子</th>
                <th scope="col">穩健 z 分數</th>
              </tr>
            </thead>
            <tbody>
              {event.drivers.map((d, i) => (
                <tr key={d.variable}>
                  <td className="num">{i + 1}</td>
                  <th scope="row">{d.label}</th>
                  <td className="num">{formatSigned(d.z, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        }
      >
        <DivergingBars rows={event.drivers.map((d) => ({ key: d.variable, label: d.label, value: d.z }))} format={(v) => formatSigned(v, 1)} />
      </ChartFrame>
      {top && (
        <p className="callout">
          高峰時同步偏離最多的因子是 <strong>{top.label}</strong>：相對這個地點同時段的典型值偏離 {formatSigned(top.z, 1)} 個穩健標準差（以中位數與 MAD 計算，不受其他極端值影響）。
        </p>
      )}

      <ChartFrame
        title="事件前後的 PM2.5"
        summary={`紅色區塊是偵測到的事件期間；來源數值高於同時段典型值。`}
        table={
          <table>
            <thead>
              <tr>
                <th scope="col">時間</th>
                <th scope="col">PM2.5</th>
                <th scope="col">典型值</th>
              </tr>
            </thead>
            <tbody>
              {event.context.map((c) => (
                <tr key={c.t}>
                  <th scope="row">{formatHour(c.t)}</th>
                  <td className="num">{formatNumber(c.pm25, 1)}</td>
                  <td className="num">{formatNumber(c.baseline, 1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        }
      >
        <MultiLine series={series} labels={event.context.map((c) => formatHour(c.t))} span={span} format={(v) => String(v)} />
      </ChartFrame>
      <Legend series={series} />

      <section aria-labelledby="similar-title">
        <h3 id="similar-title">歷史上最相似的事件</h3>
        {event.similar.length === 0 ? (
          <p className="muted">沒有其他事件可比較。</p>
        ) : (
          <ol className="similar-list" data-testid="similar-list">
            {event.similar.map((s) => {
              const other = all.get(s.event_id);
              return (
                <li key={s.event_id}>
                  <a href={routeToHash({ name: "anomalies", id: s.event_id, station: filter.station, kind: filter.kind })}>
                    {other ? `${other.station} ${formatHour(other.start)}` : s.event_id}
                  </a>{" "}
                  <span className="muted small">
                    距離 {s.distance.toFixed(2)}
                    {other && ` · ${KIND_LABEL[other.kind]} · 主要偏離 ${other.drivers[0]?.label ?? "—"}`}
                  </span>
                </li>
              );
            })}
          </ol>
        )}
        <p className="muted small">相似度以高峰時各因子的 z 分數組成的特徵向量計算（歐氏距離越小越像），也就是「異常的樣子」相不相同。</p>
      </section>
    </article>
  );
}

function AnomaliesView({ data, id, station, kind }: Props & { data: Anomalies }) {
  const [, navigate] = useRoute();
  const filtered = filterEvents(data.events, { station, kind });
  const all = new Map(data.events.map((e) => [e.id, e]));
  const selected = (id && filtered.find((e) => e.id === id)) || (id && all.get(id)) || filtered[0];
  const stations = [...new Set(data.events.map((e) => e.station))].sort((a, b) => a.localeCompare(b, "zh-Hant"));
  const v = data.validation;
  const update = (patch: Props) => navigate({ name: "anomalies", id: undefined, station, kind, ...patch }, { replace: true });

  return (
    <div className="stack">
      <header>
        <span className="eyebrow">異常偵測 · 相關因子</span>
        <h1>異常事件與相關因子</h1>
        <p className="lede">
          每個地點、每個時段各自的「正常範圍」不同。我們用中位數與 MAD 算出 PM2.5 的穩健 z 分數，超過 {data.threshold} 就標記為異常，再看其他地點有沒有在傳播延遲範圍內同時異常，區分局部與區域事件。
        </p>
      </header>

      {v && (
        <section className="kpis" aria-label="偵測器驗證">
          <div className="card kpi">
            <span className="stat-label">注入事件的召回率</span>
            <span className="stat-value" data-testid="recall">
              {formatPercent(v.recall, 0)}
            </span>
            <span className="muted small">合成資料中刻意注入 {v.injected_events} 個局部事件，偵測到的比例</span>
          </div>
          <div className="card kpi">
            <span className="stat-label">「局部」標記的精確率</span>
            <span className="stat-value">{formatPercent(v.local_precision, 0)}</span>
            <span className="muted small">{v.local_events} 個被判為局部的事件中，屬於注入事件的比例</span>
          </div>
          <div className="card kpi">
            <span className="stat-label">誠實揭露</span>
            <span className="stat-value">{v.injected_labelled_regional}</span>
            <span className="muted small">個注入的局部事件恰好與區域污染團重疊，被歸為「區域」</span>
          </div>
        </section>
      )}

      <section className="card filters" aria-label="篩選">
        <label className="field">
          <span className="label">地點</span>
          <select className="input" value={station ?? ""} onChange={(e) => update({ station: e.target.value || undefined })}>
            <option value="">全部地點</option>
            {stations.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <fieldset className="segmented">
          <legend>類型</legend>
          {([undefined, "local", "regional"] as (Kind | undefined)[]).map((k) => (
            <label key={k ?? "all"}>
              <input type="radio" name="kind" checked={kind === k} onChange={() => update({ kind: k })} />
              <span>{k ? KIND_LABEL[k] : "全部"}</span>
            </label>
          ))}
        </fieldset>
        <button
          type="button"
          className="btn"
          onClick={() =>
            downloadText(
              "anomaly-events.csv",
              toCsv(["id", "station", "kind", "start", "end", "duration_hours", "peak_aqi", "peak_pm25", "top_driver"], eventRows(filtered)),
              "text/csv;charset=utf-8",
            )
          }
          disabled={filtered.length === 0}
        >
          下載 CSV（{filtered.length} 筆）
        </button>
      </section>

      {filtered.length === 0 ? (
        <EmptyState title="沒有符合條件的事件">
          <p>換一個地點或類型試試。</p>
        </EmptyState>
      ) : (
        <div className="split anomalies-layout">
          <section aria-labelledby="events-title">
            <h2 id="events-title">事件列表（{filtered.length}）</h2>
            <ScrollRegion label="異常事件列表">
              <ul className="event-list" data-testid="event-list">
                {filtered.map((e) => (
                  <li key={e.id}>
                    <a
                      className="event-item"
                      href={routeToHash({ name: "anomalies", id: e.id, station, kind })}
                      aria-current={selected?.id === e.id ? "true" : undefined}
                    >
                      <span className="event-item-head">
                        <strong>{e.station}</strong>
                        <span className="tag" data-tone={e.kind === "local" ? "warn" : "info"}>
                          {KIND_LABEL[e.kind]}
                        </span>
                      </span>
                      <span className="small">
                        {formatHour(e.start)} · {e.duration_hours} 小時 · 高峰 AQI {formatNumber(e.peak_aqi)}
                      </span>
                      <span className="muted small">主要偏離：{e.drivers[0]?.label ?? "—"}</span>
                    </a>
                  </li>
                ))}
              </ul>
            </ScrollRegion>
          </section>
          {selected && <EventDetail key={selected.id} event={selected} all={all} filter={{ station, kind }} windowHours={data.regional_window_hours} />}
        </div>
      )}
    </div>
  );
}

export default function AnomaliesPage(props: Props) {
  useDocumentTitle("異常事件與相關因子");
  const data = useDataset("anomalies.json");
  return (
    <div className="page">
      <Gate<[Anomalies]> states={[data]}>{(d) => <AnomaliesView data={d} {...props} />}</Gate>
    </div>
  );
}
