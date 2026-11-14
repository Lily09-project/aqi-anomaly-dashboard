import type { CSSProperties } from "react";
import { useDataset, useDocumentTitle, useNow } from "../app/hooks";
import { AqiChip, ScaleLegend } from "../components/Aqi";
import { ChartFrame, TaiwanMap } from "../components/charts";
import { DataTime, StaleNotice } from "../components/Freshness";
import { Gate } from "../components/States";
import { categoryOf, futureForecast } from "../lib/air";
import { formatClock, formatHour, formatNumber, formatSigned } from "../lib/format";
import { routeToHash } from "../lib/router";
import type { Category, Overview, Propagation, Provenance, QuantileHour, Station } from "../lib/types";
import "./Home.css";

const shortName = (name: string) => name.replace(/(?:測站|網格)$/, "");

const NEXT_HOURS = 6;

/** The next six forecast hours that have not started yet; null when fewer remain. */
function nextSix(station: Station, nowMs: number): QuantileHour[] | null {
  const hours = futureForecast(station.forecast, nowMs).slice(0, NEXT_HOURS);
  return hours.length === NEXT_HOURS ? hours : null;
}

/** Highest P90 in the next six hours: the "how bad could it get" number. */
const worstOf = (hours: QuantileHour[]) => Math.max(...hours.map((f) => f.p90));

/** Highest median forecast in the next six hours. */
const medianOf = (hours: QuantileHour[]) => Math.max(...hours.map((f) => f.p50));

const formatCoordinate = (value: number | null) => (value === null ? "—" : value.toFixed(3));

/** Hour of day from a Taiwan-local timestamp ("2026-11-08T21:00…" → 21). */
const hourOf = (iso: string) => Number(iso.slice(11, 13));

interface Outlook {
  station: Station;
  future: QuantileHour[];
  peak: QuantileHour | null;
  peakIndex: number;
  /** Future hours whose median is above the sensitive-group threshold. */
  above: number;
}

function outlookOf(station: Station, nowMs: number, threshold: number): Outlook {
  const future = futureForecast(station.forecast, nowMs);
  let peakIndex = -1;
  future.forEach((f, i) => {
    if (peakIndex < 0 || f.p50 > (future[peakIndex]?.p50 ?? -Infinity)) peakIndex = i;
  });
  return { station, future, peak: future[peakIndex] ?? null, peakIndex, above: future.filter((f) => f.p50 > threshold).length };
}

/** A tick every six clock hours; midnight shows the date instead of the time. */
function tickLabel(iso: string): string {
  return hourOf(iso) === 0 ? formatHour(iso).split(" ")[0] ?? iso : formatClock(iso);
}

/** "Now → next 24 hours" for every location: one row of AQI-coloured hours per place. */
function OutlookBoard({ outlooks, categories, threshold, isModel, next }: { outlooks: Outlook[]; categories: Category[]; threshold: number; isModel: boolean; next: Map<string, QuantileHour[] | null> }) {
  const longest = outlooks.reduce<Outlook | undefined>((top, o) => (!top || o.future.length > top.future.length ? o : top), undefined);
  const columns = longest?.future.length ?? 0;
  const worst = outlooks.reduce<Outlook | undefined>((top, o) => (o.peak && (!top?.peak || o.peak.p50 > top.peak.p50) ? o : top), undefined);
  const exceeding = outlooks.filter((o) => o.above > 0);
  const worstCategory = worst?.peak ? categoryOf(worst.peak.p50, categories) : null;
  // Labels near the right edge would run past a phone screen; the data table lists every hour.
  const ticks = (longest?.future ?? []).flatMap((f, i) => (hourOf(f.t) % 6 === 0 && i <= columns - 3 ? [{ i, label: tickLabel(f.t) }] : []));

  return (
    <section className="outlook card" aria-labelledby="outlook-title">
      <header className="outlook-head">
        <h2 id="outlook-title">
          現在 <span aria-hidden="true">→</span>
          <span className="visually-hidden">到</span> 未來 {columns > 0 ? columns : 24} 小時
        </h2>
        <p className="outlook-takeaway" data-testid="outlook-takeaway">
          {worst?.peak ? (
            <>
              預估最差的是 <strong>{worst.station.station}</strong>：{formatHour(worst.peak.t)} 前後中位數 AQI {formatNumber(worst.peak.p50)}
              {worstCategory ? `（${worstCategory.label}）` : ""}。
              {exceeding.length > 0
                ? `${outlooks.length} 個地點中有 ${exceeding.length} 個會有時段的中位數超過敏感族群門檻 ${threshold}。`
                : `${outlooks.length} 個地點的中位數都不超過敏感族群門檻 ${threshold}。`}
            </>
          ) : (
            "目前資料已沒有尚未發生的預報時段，等下次資料更新後再看。"
          )}
        </p>
      </header>

      <ChartFrame
        interactive
        title={`各${isModel ? "模型格點" : "測站"}逐時預報（色塊為中位數 P50 的 AQI 分級，上緣細條為 P90）`}
        summary={outlooks
          .map((o) => (o.peak ? `${o.station.station} 現在 ${formatNumber(o.station.aqi)}，未來最高 ${formatNumber(o.peak.p50)}（${formatHour(o.peak.t)}）` : `${o.station.station} 現在 ${formatNumber(o.station.aqi)}，沒有未來預報`))
          .join("；")}
        legend={
          <div className="outlook-legend">
            <ScaleLegend categories={categories} />
            <p className="muted small">
              每格一小時，顏色依預報中位數（P50）分級；上緣細條依 P90（十次約一次會更糟）分級。外框標出各地點的最高時段。
            </p>
          </div>
        }
        table={
          <table data-testid="outlook-table">
            <thead>
              <tr>
                <th scope="col">時間</th>
                {outlooks.map((o) => (
                  <th scope="col" key={o.station.station}>
                    {shortName(o.station.station)} P50（P10–P90）
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(longest?.future ?? []).map((f, i) => (
                <tr key={f.t}>
                  <th scope="row">{formatHour(f.t)}</th>
                  {outlooks.map((o) => {
                    const hour = o.future[i];
                    return (
                      <td className="num" key={o.station.station}>
                        {hour ? `${formatNumber(hour.p50)}（${formatNumber(hour.p10)}–${formatNumber(hour.p90)}）` : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        }
      >
        <div className="outlook-grid" style={{ "--hours": Math.max(columns, 1) } as CSSProperties}>
          <div className="outlook-axis" aria-hidden="true">
            <span className="outlook-axis-now">現在</span>
            <span className="outlook-axis-ticks">
              {ticks.map((t) => (
                <span key={t.i} style={{ gridColumn: `${t.i + 1}` }}>
                  {t.label}
                </span>
              ))}
            </span>
          </div>
          <ul className="station-list">
            {outlooks.map((o) => {
              const six = next.get(o.station.station);
              return (
                <li key={o.station.station}>
                  <a className="station-card" href={routeToHash({ name: "station", station: o.station.station })}>
                    <span className="now-tile" data-category={categoryOf(o.station.aqi, categories)?.key ?? "none"}>
                      <span className="now-tile-label">現在</span>
                      <span className="now-tile-value">{formatNumber(o.station.aqi)}</span>
                    </span>
                    <span className="station-name">
                      <strong>{o.station.station}</strong>
                      <span className="station-sub small">
                        {o.station.county} · {categoryOf(o.station.aqi, categories)?.label ?? o.station.category_label}
                      </span>
                    </span>
                    <span className="strip" aria-hidden="true">
                      {o.future.map((f, i) => (
                        <span
                          key={f.t}
                          className={i === o.peakIndex ? "cell is-peak" : "cell"}
                          data-category={categoryOf(f.p50, categories)?.key ?? "none"}
                          data-day-start={hourOf(f.t) === 0 ? "true" : undefined}
                        >
                          <span className="cell-p90" data-category={categoryOf(f.p90, categories)?.key ?? "none"} />
                        </span>
                      ))}
                    </span>
                    <span className="station-meta small">
                      {o.peak ? (
                        <>
                          最高 <strong>{formatNumber(o.peak.p50)}</strong>（{formatHour(o.peak.t)}）
                        </>
                      ) : (
                        "沒有未來預報"
                      )}
                      <span className="station-meta-extra">
                        <span className="meta-sep"> · </span>PM2.5 {formatNumber(o.station.pm25, 1)} · 風速 {formatNumber(o.station.wind_speed, 1)} m/s ·{" "}
                        {six ? `6 小時 P90 ${formatNumber(worstOf(six))}` : "未來預報不足 6 小時"}
                      </span>
                    </span>
                  </a>
                </li>
              );
            })}
          </ul>
        </div>
      </ChartFrame>
    </section>
  );
}

function Dashboard({ overview, propagation, provenance }: { overview: Overview; propagation: Propagation; provenance: Provenance }) {
  const nowMs = useNow();
  const stations = [...overview.stations].sort((a, b) => b.aqi - a.aqi);
  const worst = stations[0];
  const threshold = overview.planner_thresholds.sensitive;
  const next = new Map(overview.stations.map((s) => [s.station, nextSix(s, nowMs)]));
  const outlooks = stations.map((s) => outlookOf(s, nowMs, threshold));
  const risings = overview.stations.flatMap((s) => {
    const hours = next.get(s.station);
    return hours ? [{ station: s, median: medianOf(hours), worst: worstOf(hours), rise: medianOf(hours) - s.aqi }] : [];
  });
  const rising = risings.sort((a, b) => b.rise - a.rise)[0];
  const upstream = worst ? propagation.nearest_upstream[worst.station] : undefined;
  const upstreamStation = upstream ? overview.stations.find((s) => s.station === upstream.upstream) : undefined;
  const isModel = provenance.is_model_estimate === true;

  return (
    <div className="home">
      <header className="hero">
        <span className="eyebrow">
          <span className="eyebrow-kicker">空氣品質實驗室 · </span>
          <DataTime latest={overview.latest} nowMs={nowMs} />
        </span>
        <h1>空氣會移動，預報也該告訴你不確定性。</h1>
        <div className="hero-brief">
        <p className="lede">
          {isModel
            ? `用 ${overview.stations.length} 個 CAMS 區域模型格點回答三件事：現在哪裡空氣最差、未來 24 小時可能多糟（附 80% 預測區間）、哪些時段異常偏高，以及當時哪些因子一起偏離。`
            : provenance.is_simulated
              ? "使用固定種子測試資料驗證預報、時序關聯、異常偵測與情境分析。"
              : "整理公開空品資料，查看風險趨勢、預報區間、異常事件與情境分析。"}
        </p>
        <p className="hero-source small">
          {isModel
            ? "資料：Open-Meteo · CAMS Global 模型估算，非環境部測站實測，也不是健康警示。"
            : provenance.is_simulated
              ? "資料：固定種子測試資料，只用於測試與預覽。"
              : `資料：${provenance.data_source}。`}{" "}
          <a href={routeToHash({ name: "data" })}>方法與資料可信度</a>
        </p>
        </div>
        {worst && (
          <div className="hero-actions">
            <a className="btn btn-primary" href={routeToHash({ name: "station", station: worst.station })}>
              從{shortName(worst.station)}的 24 小時預報開始 →
            </a>
            <a className="btn" href={routeToHash({ name: "planner" })}>比較兩地時段</a>
            <a className="btn" href={routeToHash({ name: "anomalies" })}>
              看異常事件
            </a>
          </div>
        )}
      </header>

      {isModel && <StaleNotice latest={overview.latest} nowMs={nowMs} />}

      <OutlookBoard outlooks={outlooks} categories={overview.categories} threshold={threshold} isModel={isModel} next={next} />

      <section className="insights" aria-label="重點">
        {worst && (
          <a className="card insight" href={routeToHash({ name: "station", station: worst.station })}>
            <span className="stat-label">目前最高</span>
            <strong className="insight-title">{worst.station}</strong>
            <AqiChip value={worst.aqi} categories={overview.categories} />
            <span className="insight-more small">查看 24 小時機率預報與出門時段 →</span>
          </a>
        )}
        {worst && upstream && (
          <a className="card insight" href={routeToHash({ name: "propagation" })} data-testid="upstream-insight">
            <span className="stat-label">上游訊號</span>
            <strong className="insight-title">
              {shortName(worst.station)} 通常落後 {shortName(upstream.upstream)} 約 {upstream.lag_hours} 小時
            </strong>
            <span>
              {shortName(upstream.upstream)} 現在 <AqiChip value={upstreamStation?.aqi ?? null} categories={overview.categories} />
            </span>
            <span className="insight-more small">由去季節化互相關找出的領先關係 →</span>
          </a>
        )}
        {rising ? (
          <a className="card insight" href={routeToHash({ name: "station", station: rising.station.station })}>
            <span className="stat-label">未來 6 小時預估上升最多</span>
            <strong className="insight-title">
              {rising.station.station}（{formatSigned(rising.rise, 0)}）
            </strong>
            <span>
              預估中位數最高 <AqiChip value={rising.median} categories={overview.categories} />
            </span>
            <span className="insight-more small">最壞情境（P90，十次約一次會更糟）{formatNumber(rising.worst)} →</span>
          </a>
        ) : (
          <div className="card insight" data-testid="rising-insufficient">
            <span className="stat-label">未來 6 小時預估上升最多</span>
            <strong className="insight-title">未來預報不足 6 小時</strong>
            <span className="insight-more small">目前資料已沒有足夠的未來時段，等下次資料更新後再比較。</span>
          </div>
        )}
      </section>

      <div className="home-lower">
        <section className="card home-map" aria-labelledby="map-title">
          <h2 id="map-title" className="section-title">
            {isModel ? "模型格點在哪裡" : "測站在哪裡"}
          </h2>
          <ChartFrame
            interactive
            title={isModel ? "區域模型格點分布與目前 AQI" : "測站分布與目前 AQI"}
            summary={stations.map((s) => `${s.station} ${formatNumber(s.aqi)}（${s.category_label}）`).join("、")}
            table={
              <table>
                <thead>
                  <tr>
                    <th scope="col">{isModel ? "模型格點" : "測站"}</th>
                    <th scope="col">縣市</th>
                    <th scope="col">AQI</th>
                    <th scope="col">分級</th>
                    <th scope="col">經緯度</th>
                  </tr>
                </thead>
                <tbody>
                  {stations.map((s) => (
                    <tr key={s.station}>
                      <th scope="row">{s.station}</th>
                      <td>{s.county}</td>
                      <td className="num">{formatNumber(s.aqi)}</td>
                      <td>{s.category_label}</td>
                      <td>
                        {formatCoordinate(s.latitude)}, {formatCoordinate(s.longitude)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
          >
            <TaiwanMap
              stations={overview.stations.map((s) => ({
                name: s.station,
                lon: s.longitude,
                lat: s.latitude,
                category: categoryOf(s.aqi, overview.categories)?.key ?? null,
                label: `${shortName(s.station)} ${formatNumber(s.aqi)}`,
                emphasis: s.station === worst?.station,
              }))}
              hrefFor={(station) => routeToHash({ name: "station", station })}
            />
          </ChartFrame>
        </section>

        <section aria-labelledby="tour-title" className="tour">
          <h2 id="tour-title" className="section-title">
            四個分析頁，各回答一個問題
          </h2>
          <ol className="tour-list">
            <li>
              <a className="tour-card" href={routeToHash({ name: "propagation" })}>
                <span className="tour-no" aria-hidden="true">01</span>
                <strong>時序關聯</strong>
                <span className="tour-q">哪個地點的 PM2.5 先變化？</span>
                <span className="muted small">
                  {propagation.links.length
                    ? `目前找到 ${propagation.links.length} 組達門檻的領先關係，可逐時回放。`
                    : "目前沒有達門檻的領先關係；仍可逐時回放各地點變化。"}
                </span>
              </a>
            </li>
            <li>
              <a className="tour-card" href={routeToHash({ name: "anomalies" })}>
                <span className="tour-no" aria-hidden="true">02</span>
                <strong>異常事件</strong>
                <span className="tour-q">什麼時候異常偏高？和什麼一起偏離？</span>
                <span className="muted small">以穩健 z 分數標記事件，區分局部與區域，並找出歷史相似事件。</span>
              </a>
            </li>
            <li>
              <a className="tour-card" href={routeToHash({ name: "whatif" })}>
                <span className="tour-no" aria-hidden="true">03</span>
                <strong>情境模擬</strong>
                <span className="tour-q">條件改變時，下一小時 AQI 會怎麼變？</span>
                <span className="muted small">拖動風速、臭氧等滑桿，看每個條件把預測推高或拉低多少。</span>
              </a>
            </li>
            <li>
              <a className="tour-card" href={routeToHash({ name: "model" })}>
                <span className="tour-no" aria-hidden="true">04</span>
                <strong>模型監控</strong>
                <span className="tour-q">這些預報值得相信嗎？</span>
                <span className="muted small">和「維持現狀」「同時段典型值」兩個基準比誤差，並檢查區間覆蓋率。</span>
              </a>
            </li>
          </ol>
        </section>
      </div>
    </div>
  );
}

export default function Home() {
  useDocumentTitle("");
  const overview = useDataset("overview.json");
  const propagation = useDataset("propagation.json");
  const provenance = useDataset("provenance.json");
  return (
    <div className="page">
      <Gate<[Overview, Propagation, Provenance]> states={[overview, propagation, provenance]}>{(o, p, d) => <Dashboard overview={o} propagation={p} provenance={d} />}</Gate>
    </div>
  );
}
