import { useDataset, useDocumentTitle, useNow, useRoute } from "../app/hooks";
import { AqiChip } from "../components/Aqi";
import { ChartFrame, ForecastBand } from "../components/charts";
import { EmptyState, Gate } from "../components/States";
import { ADVICE, bestWindow, categoryOf, exceedanceProbability, futureForecast, windowRisks } from "../lib/air";
import { addHours, formatClock, formatHour, formatNumber, formatPercent } from "../lib/format";
import { routeToHash, type Sensitivity } from "../lib/router";
import type { Model, Overview, Provenance } from "../lib/types";
import "./Station.css";

const HISTORY_SHOWN = 48;
const DURATIONS = [1, 2, 3, 4, 6, 8, 12];
const AUDIENCE: Record<Sensitivity, string> = { sensitive: "敏感族群", general: "一般民眾" };

interface Props {
  station: string;
  sensitivity: Sensitivity;
  hours: number;
}

function StationView({ overview, model, provenance, station: name, sensitivity, hours }: Props & { overview: Overview; model: Model; provenance: Provenance }) {
  const [, navigate] = useRoute();
  const nowMs = useNow();
  const station = overview.stations.find((s) => s.station === name);
  const locationLabel = provenance.is_model_estimate ? "模型格點" : "測站";
  if (!station) {
    return (
      <EmptyState title={"找不到這個" + locationLabel}>
        <p>
          「{name}」不在資料中。<a href={routeToHash({ name: "home" })}>回到總覽</a>選擇{locationLabel}。
        </p>
      </EmptyState>
    );
  }

  const threshold = overview.planner_thresholds[sensitivity];
  const forecast = station.forecast;
  const availableForecast = futureForecast(forecast, nowMs);
  const best = bestWindow(availableForecast, hours, threshold);
  const risks = windowRisks(availableForecast, hours, threshold);
  const worstRisk = risks.length ? Math.max(...risks) : null;
  const worstStart = worstRisk === null ? -1 : risks.indexOf(worstRisk);
  const category = categoryOf(station.aqi, overview.categories);
  const advice = category ? ADVICE[category.key] : undefined;
  const coverage = model.horizons.map((h) => h.coverage);
  const update = (patch: Partial<Props>) =>
    navigate({ name: "station", station: name, sensitivity, hours, ...patch }, { replace: true });

  const windowStart = best ? availableForecast[best.start] : undefined;
  const windowEnd = best ? availableForecast[best.start + hours - 1] : undefined;
  const chartWindowStart = windowStart ? forecast.findIndex((item) => item.h === windowStart.h) : -1;

  return (
    <div className="stack">
      <header className="station-head">
        <div>
          <span className="eyebrow">{station.county} · 資料時間 {formatHour(overview.latest)}</span>
          <h1>{station.station}</h1>
        </div>
        <label className="field station-switch">
          <span className="label">切換{locationLabel}</span>
          <select
            className="input"
            value={station.station}
            onChange={(e) => navigate({ name: "station", station: e.target.value, sensitivity, hours })}
          >
            {overview.stations.map((s) => (
              <option key={s.station} value={s.station}>
                {s.station}
              </option>
            ))}
          </select>
        </label>
      </header>

      <section className="grid grid-3" aria-label="目前狀態">
        <div className="card kpi">
          <span className="stat-label">{provenance.is_model_estimate ? "目前美國 AQI" : "目前 AQI"}</span>
          <span className="aqi-big" data-testid="current-aqi">
            {formatNumber(station.aqi)}
          </span>
          <AqiChip value={station.aqi} categories={overview.categories} />
        </div>
        <div className="card kpi">
          <span className="stat-label">污染物與氣象</span>
          <dl className="mini-dl">
            <dt>PM2.5</dt>
            <dd>{formatNumber(station.pm25, 1)} µg/m³</dd>
            <dt>PM10</dt>
            <dd>{formatNumber(station.pm10, 1)} µg/m³</dd>
            <dt>臭氧</dt>
            <dd>{formatNumber(station.o3, 1)} {provenance.ozone_unit ?? "ppb"}</dd>
            <dt>風速</dt>
            <dd>{formatNumber(station.wind_speed, 1)} m/s</dd>
          </dl>
        </div>
        <div className="card kpi">
          <span className="stat-label">{AUDIENCE[sensitivity]}活動建議</span>
          <p data-testid="advice">{advice ? advice[sensitivity] : "無資料"}</p>
          <span className="muted small">{provenance.is_model_estimate ? "參考美國 AQI 分級 · 模型估算" : "依環境部 AQI 分級的活動建議改寫"}</span>
        </div>
      </section>

      <section className="card planner" aria-labelledby="planner-title">
        <h2 id="planner-title">最佳出門時段</h2>
        <div className="planner-controls">
          <fieldset className="segmented">
            <legend>誰要出門</legend>
            {(Object.keys(AUDIENCE) as Sensitivity[]).map((key) => (
              <label key={key}>
                <input type="radio" name="sensitivity" value={key} checked={sensitivity === key} onChange={() => update({ sensitivity: key })} />
                <span>{AUDIENCE[key]}</span>
              </label>
            ))}
          </fieldset>
          <p className="muted small planner-threshold">
            超標門檻：AQI &gt; {threshold}（{AUDIENCE[sensitivity]}）
          </p>
          <label className="field">
            <span className="label">活動時長</span>
            <select className="input" value={hours} onChange={(e) => update({ hours: Number(e.target.value) })}>
              {DURATIONS.map((d) => (
                <option key={d} value={d}>
                  {d} 小時
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="planner-result" aria-live="polite" data-testid="planner-result">
          {best && windowStart && windowEnd ? (
            <>
              <p className="planner-answer">
                建議 <strong data-testid="best-window" data-window-start={windowStart.t}>{formatHour(windowStart.t)}–{formatClock(addHours(windowEnd.t, 1))}</strong>
                ，平均超標機率 <strong data-testid="best-risk">{formatPercent(best.risk, 1)}</strong>
              </p>
              <p className="muted">
                以尚未發生的 {availableForecast.length} 個預報時點比較 {risks.length} 個連續 {hours} 小時候選時段，這一段平均超標機率最低、預估中位數 AQI 約{" "}
                {formatNumber(best.meanP50)}。
                {worstRisk !== null && worstRisk - best.risk > 0.005 && availableForecast[worstStart] && (
                  <> 最該避開的是 {formatHour(availableForecast[worstStart].t)} 起的時段（{formatPercent(worstRisk, 1)}）。</>
                )}
              </p>
            </>
          ) : (
            <p>目前剩餘的未來預報不足以安排 {hours} 小時活動。</p>
          )}
        </div>

        <ChartFrame
          title={`${station.station} 過去 ${HISTORY_SHOWN} 小時與資料時間起算的 24 小時預報`}
          summary={(provenance.is_model_estimate ? "實線為每 3 小時模型估算值與時點間插值" : "實線為來源資料") + "、虛線為預報中位數，陰影為 80% 預測區間；紅線是" + AUDIENCE[sensitivity] + "門檻 " + threshold + (best ? "，綠色區塊是建議時段" : "") + "；最佳時段只比較尚未發生的預報。"}
          table={
            <table data-testid="forecast-table" data-as-of-ms={nowMs}>
              <thead>
                <tr>
                  <th scope="col">時間</th>
                  <th scope="col">P10</th>
                  <th scope="col">P50</th>
                  <th scope="col">P90</th>
                  <th scope="col">超標機率</th>
                </tr>
              </thead>
              <tbody>
                {availableForecast.length ? availableForecast.map((f) => (
                  <tr key={f.h} data-forecast-time={f.t}>
                    <th scope="row">{formatHour(f.t)}</th>
                    <td className="num">{formatNumber(f.p10)}</td>
                    <td className="num">{formatNumber(f.p50)}</td>
                    <td className="num">{formatNumber(f.p90)}</td>
                    <td className="num">{formatPercent(exceedanceProbability(f, threshold), 1)}</td>
                  </tr>
                )) : (
                  <tr><td colSpan={5}>目前沒有尚未發生的預報時段。</td></tr>
                )}
              </tbody>
            </table>
          }
        >
          {forecast.length ? (
            <ForecastBand
              history={station.history.slice(-HISTORY_SHOWN).map((h) => ({ label: formatHour(h.t), value: h.aqi }))}
              forecast={forecast.map((f) => ({ label: formatHour(f.t), p10: f.p10, p50: f.p50, p90: f.p90 }))}
              threshold={threshold}
              window={best && chartWindowStart >= 0 ? { start: chartWindowStart, hours } : null}
            />
          ) : (
            <p className="muted">目前沒有可繪製的模型預報資料。</p>
          )}
        </ChartFrame>
        <p className="muted small">
          區間怎麼來：每個預報時距各有一個 ridge 迴歸模型，再用保留的校準期殘差（分割式保形預測）決定 P10／P90。測試期的 80% 區間實際涵蓋{" "}
          {formatPercent(Math.min(...coverage), 0)}–{formatPercent(Math.max(...coverage), 0)} 的觀測值。
          <a href={routeToHash({ name: "model" })}>查看模型監控</a>
        </p>
      </section>
    </div>
  );
}

export default function Station(props: Props) {
  useDocumentTitle(props.station);
  const overview = useDataset("overview.json");
  const model = useDataset("model.json");
  const provenance = useDataset("provenance.json");
  return (
    <div className="page">
      <Gate<[Overview, Model, Provenance]> states={[overview, model, provenance]}>{(o, m, p) => <StationView overview={o} model={m} provenance={p} {...props} />}</Gate>
    </div>
  );
}
