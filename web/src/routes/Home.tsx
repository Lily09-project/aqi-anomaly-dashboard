import { useDataset, useDocumentTitle, useNow } from "../app/hooks";
import { AqiChip, ScaleLegend } from "../components/Aqi";
import { ChartFrame, TaiwanMap } from "../components/charts";
import { DataTime, StaleNotice } from "../components/Freshness";
import { Gate } from "../components/States";
import { categoryOf, futureForecast } from "../lib/air";
import { formatNumber, formatSigned } from "../lib/format";
import { routeToHash } from "../lib/router";
import type { Overview, Propagation, Provenance, QuantileHour, Station } from "../lib/types";
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

function Dashboard({ overview, propagation, provenance }: { overview: Overview; propagation: Propagation; provenance: Provenance }) {
  const nowMs = useNow();
  const stations = [...overview.stations].sort((a, b) => b.aqi - a.aqi);
  const worst = stations[0];
  const next = new Map(overview.stations.map((s) => [s.station, nextSix(s, nowMs)]));
  const outlooks = overview.stations.flatMap((s) => {
    const hours = next.get(s.station);
    return hours ? [{ station: s, median: medianOf(hours), worst: worstOf(hours), rise: medianOf(hours) - s.aqi }] : [];
  });
  const rising = outlooks.sort((a, b) => b.rise - a.rise)[0];
  const upstream = worst ? propagation.nearest_upstream[worst.station] : undefined;
  const upstreamStation = upstream ? overview.stations.find((s) => s.station === upstream.upstream) : undefined;

  return (
    <div className="stack">
      <header className="hero">
        <span className="eyebrow">
          空氣品質實驗室 · <DataTime latest={overview.latest} nowMs={nowMs} />
        </span>
        <h1>空氣會移動，預報也該告訴你不確定性。</h1>
        <p className="lede">
          {provenance.is_model_estimate
            ? `用 ${overview.stations.length} 個 CAMS 區域模型格點回答三件事：現在哪裡空氣最差、未來 24 小時可能多糟（附 80% 預測區間）、哪些時段異常偏高，以及當時哪些因子一起偏離。`
            : provenance.is_simulated
              ? "使用固定種子測試資料驗證預報、時序關聯、異常偵測與情境分析。"
              : "整理公開空品資料，查看風險趨勢、預報區間、異常事件與情境分析。"}
        </p>
        {worst && (
          <div className="hero-actions">
            <a className="btn btn-primary" href={routeToHash({ name: "station", station: worst.station })}>
              從{shortName(worst.station)}的 24 小時預報開始 →
            </a>
            <a className="btn" href={routeToHash({ name: "anomalies" })}>
              看異常事件
            </a>
          </div>
        )}
        {provenance.is_model_estimate && <StaleNotice latest={overview.latest} nowMs={nowMs} />}
        <p className="hero-source small">
          {provenance.is_model_estimate
            ? "資料：Open-Meteo · CAMS Global 模型估算，非環境部測站實測，也不是健康警示。"
            : provenance.is_simulated
              ? "資料：固定種子測試資料，只用於測試與預覽。"
              : `資料：${provenance.data_source}。`}{" "}
          <a href={routeToHash({ name: "data" })}>方法與資料可信度</a>
        </p>
      </header>

      <section className="grid grid-3" aria-label="重點">
        {worst && (
          <a className="card insight" href={routeToHash({ name: "station", station: worst.station })}>
            <span className="stat-label">目前最高</span>
            <strong className="insight-title">{worst.station}</strong>
            <AqiChip value={worst.aqi} categories={overview.categories} />
            <span className="muted small">查看 24 小時機率預報與出門時段 →</span>
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
            <span className="muted small">由去季節化互相關找出的領先關係 →</span>
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
            <span className="muted small">最壞情境（P90，十次約一次會更糟）{formatNumber(rising.worst)} →</span>
          </a>
        ) : (
          <div className="card insight" data-testid="rising-insufficient">
            <span className="stat-label">未來 6 小時預估上升最多</span>
            <strong className="insight-title">未來預報不足 6 小時</strong>
            <span className="muted small">目前資料已沒有足夠的未來時段，等下次資料更新後再比較。</span>
          </div>
        )}
      </section>

      <section aria-labelledby="tour-title" className="tour">
        <h2 id="tour-title">四個分析頁，各回答一個問題</h2>
        <ul className="tour-list">
          <li>
            <a className="tour-card" href={routeToHash({ name: "propagation" })}>
              <strong>時序關聯</strong>
              <span>哪個地點的 PM2.5 先變化？</span>
              <span className="muted small">
                {propagation.links.length
                  ? `目前找到 ${propagation.links.length} 組達門檻的領先關係，可逐時回放。`
                  : "目前沒有達門檻的領先關係；仍可逐時回放各地點變化。"}
              </span>
            </a>
          </li>
          <li>
            <a className="tour-card" href={routeToHash({ name: "anomalies" })}>
              <strong>異常事件</strong>
              <span>什麼時候異常偏高？和什麼一起偏離？</span>
              <span className="muted small">以穩健 z 分數標記事件，區分局部與區域，並找出歷史相似事件。</span>
            </a>
          </li>
          <li>
            <a className="tour-card" href={routeToHash({ name: "whatif" })}>
              <strong>情境模擬</strong>
              <span>條件改變時，下一小時 AQI 會怎麼變？</span>
              <span className="muted small">拖動風速、臭氧等滑桿，看每個條件把預測推高或拉低多少。</span>
            </a>
          </li>
          <li>
            <a className="tour-card" href={routeToHash({ name: "model" })}>
              <strong>模型監控</strong>
              <span>這些預報值得相信嗎？</span>
              <span className="muted small">和「維持現狀」「同時段典型值」兩個基準比誤差，並檢查區間覆蓋率。</span>
            </a>
          </li>
        </ul>
      </section>

      <section className="split">
        <div className="card home-map">
          <ChartFrame
            interactive
            title={provenance.is_model_estimate ? "區域模型格點分布與目前 AQI" : "測站分布與目前 AQI"}
            legend={<ScaleLegend categories={overview.categories} />}
            summary={stations.map((s) => `${s.station} ${formatNumber(s.aqi)}（${s.category_label}）`).join("、")}
            table={
              <table>
                <thead>
                  <tr>
                    <th scope="col">{provenance.is_model_estimate ? "模型格點" : "測站"}</th>
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
        </div>

        <section aria-labelledby="station-list-title">
          <h2 id="station-list-title">{provenance.is_model_estimate ? "模型格點" : "測站"}</h2>
          <ul className="station-list">
            {stations.map((s) => {
              const hours = next.get(s.station);
              return (
                <li key={s.station}>
                  <a className="station-card" href={routeToHash({ name: "station", station: s.station })}>
                    <span className="station-name">
                      <strong>{s.station}</strong>
                      <span className="muted small">{s.county}</span>
                    </span>
                    <AqiChip value={s.aqi} categories={overview.categories} />
                    <span className="station-meta small">
                      PM2.5 {formatNumber(s.pm25, 1)} · 風速 {formatNumber(s.wind_speed, 1)} m/s · {hours ? `6 小時 P90 ${formatNumber(worstOf(hours))}` : "未來預報不足 6 小時"}
                    </span>
                  </a>
                </li>
              );
            })}
          </ul>
        </section>
      </section>
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
