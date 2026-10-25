import { useDataset, useDocumentTitle } from "../app/hooks";
import { AqiChip, ScaleLegend } from "../components/Aqi";
import { ChartFrame, TaiwanMap } from "../components/charts";
import { Gate } from "../components/States";
import { categoryOf } from "../lib/air";
import { formatHour, formatNumber, formatSigned } from "../lib/format";
import { routeToHash } from "../lib/router";
import type { Overview, Propagation, Provenance, Station } from "../lib/types";
import "./Home.css";

const shortName = (name: string) => name.replace(/(?:測站|網格)$/, "");

/** Highest P90 in the next six hours: the "how bad could it get" number. */
function nextSixWorst(station: Station): number {
  return Math.max(...station.forecast.slice(0, 6).map((f) => f.p90));
}

/** Highest median forecast in the next six hours. */
function nextSixMedian(station: Station): number {
  return Math.max(...station.forecast.slice(0, 6).map((f) => f.p50));
}

function Dashboard({ overview, propagation, provenance }: { overview: Overview; propagation: Propagation; provenance: Provenance }) {
  const stations = [...overview.stations].sort((a, b) => b.aqi - a.aqi);
  const worst = stations[0];
  const rise = (s: Station) => nextSixMedian(s) - s.aqi;
  const rising = [...overview.stations].sort((a, b) => rise(b) - rise(a))[0];
  const upstream = worst ? propagation.nearest_upstream[worst.station] : undefined;
  const upstreamStation = upstream ? overview.stations.find((s) => s.station === upstream.upstream) : undefined;

  return (
    <div className="stack">
      <header className="hero">
        <span className="eyebrow">空氣品質實驗室 · 資料時間 {formatHour(overview.latest)}</span>
        <h1>空氣會移動，預報也該告訴你不確定性。</h1>
        <p className="lede">
          {provenance.is_model_estimate
            ? overview.stations.length + " 個 CAMS 區域模型格點，提供風險趨勢、時序關聯與情境分析；不代表測站實測或污染來源判定。"
            : provenance.is_simulated ? "使用固定種子測試資料驗證預報、時序關聯與情境分析。" : "整理公開空品資料，查看風險趨勢、時序關聯與情境分析。"}
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
        {rising && (
          <a className="card insight" href={routeToHash({ name: "station", station: rising.station })}>
            <span className="stat-label">未來 6 小時預估上升最多</span>
            <strong className="insight-title">
              {rising.station}（{formatSigned(rise(rising), 0)}）
            </strong>
            <span>
              預估中位數最高 <AqiChip value={nextSixMedian(rising)} categories={overview.categories} />
            </span>
            <span className="muted small">最壞情境（P90，十次約一次會更糟）{formatNumber(nextSixWorst(rising))} →</span>
          </a>
        )}
      </section>

      <section className="split">
        <div className="card">
          <ChartFrame
            interactive
            title={provenance.is_model_estimate ? "區域模型格點分布與目前 AQI" : "測站分布與目前 AQI"}
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
                        {s.latitude.toFixed(3)}, {s.longitude.toFixed(3)}
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
          <ScaleLegend categories={overview.categories} />
        </div>

        <section aria-labelledby="station-list-title">
          <h2 id="station-list-title">{provenance.is_model_estimate ? "模型格點" : "測站"}</h2>
          <ul className="station-list">
            {stations.map((s) => {
              const peak = nextSixWorst(s);
              return (
                <li key={s.station}>
                  <a className="station-card" href={routeToHash({ name: "station", station: s.station })}>
                    <span className="station-name">
                      <strong>{s.station}</strong>
                      <span className="muted small">{s.county}</span>
                    </span>
                    <AqiChip value={s.aqi} categories={overview.categories} />
                    <span className="station-meta small">
                      PM2.5 {formatNumber(s.pm25, 1)} · 風速 {formatNumber(s.wind_speed, 1)} m/s · 6 小時 P90 {formatNumber(peak)}
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
