import { useDataset, useDocumentTitle, useNow, useRoute } from "../app/hooks";
import { Chapter } from "../components/Chapter";
import { ChartFrame, ForecastBand, Legend, type LegendItem } from "../components/charts";
import { DataTime, StaleNotice } from "../components/Freshness";
import { EmptyState, Gate } from "../components/States";
import { ADVICE, bestWindow, categoryOf, exceedanceProbability, futureForecast, windowRisks } from "../lib/air";
import { addHours, formatClock, formatHour, formatNumber, formatPercent } from "../lib/format";
import { routeToHash, type Sensitivity } from "../lib/router";
import type { Model, Overview, Provenance } from "../lib/types";
import "./Station.css";

const HISTORY_SHOWN = 48;
const DURATIONS = [1, 2, 3, 4, 6, 8, 12];
const AUDIENCE: Record<Sensitivity, string> = { sensitive: "敏感族群", general: "一般民眾" };
/** At or above this average exceedance risk, even the best window is "least bad", not "recommended". */
const HIGH_RISK = 0.5;

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
      <EmptyState title={"找不到這個" + locationLabel} asPageTitle>
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
  const forecastLegend: LegendItem[] = [
    { key: "history", label: provenance.is_model_estimate ? "過去模型估算" : "過去資料", mark: "history" },
    { key: "median", label: "點預測（P50）", mark: "median" },
    { key: "band", label: "80% 預測區間（P10–P90）", mark: "band" },
    { key: "threshold", label: `${AUDIENCE[sensitivity]}門檻 ${threshold}`, mark: "threshold" },
    ...(best && chartWindowStart >= 0 ? [{ key: "window", label: best.risk >= HIGH_RISK ? "相對最低時段" : "建議時段", mark: "window" as const }] : []),
  ];

  const answer =
    best && windowStart && windowEnd ? (
      <>
        {best.risk >= HIGH_RISK ? "相對最低" : "建議"}{" "}
        <strong data-testid="best-window" data-window-start={windowStart.t}>
          {formatHour(windowStart.t)}–{formatClock(addHours(windowEnd.t, 1))}
        </strong>
        ，平均超標機率 <strong data-testid="best-risk">{formatPercent(best.risk, 1)}</strong>。
      </>
    ) : (
      <>目前剩餘的未來預報不足以安排 {hours} 小時活動。</>
    );

  return (
    <div className="stack">
      <header className="station-head">
        <div className="station-title">
          <span className="eyebrow">
            {station.county} · <DataTime latest={overview.latest} nowMs={nowMs} />
          </span>
          <h1>{station.station}</h1>
          <a className="btn" href={routeToHash({ name: "planner", a: station.station, hours, threshold })}>比較另一個地點</a>
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

      {provenance.is_model_estimate && <StaleNotice latest={overview.latest} nowMs={nowMs} />}

      <section className="now-panel" aria-label="目前狀態">
        <div className="now-main" data-category={category?.key ?? "none"}>
          <span className="now-main-label">{provenance.is_model_estimate ? "目前美國 AQI" : "目前 AQI"}</span>
          <span className="aqi-big" data-testid="current-aqi">
            {formatNumber(station.aqi)}
          </span>
          <span className="now-main-cat">{category?.label ?? "無資料"}</span>
        </div>
        <div className="now-cell">
          <span className="stat-label">污染物與氣象</span>
          <dl className="mini-dl">
            <dt>PM2.5</dt>
            <dd>{formatNumber(station.pm25, 1)} µg/m³</dd>
            <dt>PM10</dt>
            <dd>{formatNumber(station.pm10, 1)} µg/m³</dd>
            <dt>臭氧</dt>
            <dd>
              {formatNumber(station.o3, 1)} {provenance.ozone_unit ?? "ppb"}
            </dd>
            <dt>風速</dt>
            <dd>{formatNumber(station.wind_speed, 1)} m/s</dd>
          </dl>
        </div>
        <div className="now-cell now-advice">
          <span className="stat-label">{AUDIENCE[sensitivity]}活動建議</span>
          <p data-testid="advice">{advice ? advice[sensitivity] : "無資料"}</p>
          <span className="muted small">{provenance.is_model_estimate ? "參考美國 AQI 分級 · 模型估算" : "依環境部 AQI 分級的活動建議改寫"}</span>
        </div>
      </section>

      <Chapter
        no="01"
        title="最佳出門時段"
        className="planner"
        takeaway={answer}
        liveTakeaway
        howTo={
          <>
            <p>
              實線是過去 {HISTORY_SHOWN} 小時，虛線是點預測，陰影是 目標覆蓋率為 80% 的預測區間。紅色虛線是{AUDIENCE[sensitivity]}門檻，綠色區塊是比較後挑出的時段。
            </p>
            <p>
              區間怎麼來：每個預報時距各有一個 ridge 迴歸模型，P50 就是它的預報值；P10／P90 是往上下各取校準期預報誤差絕對值的第 80 百分位（分割式保形預測）。測試期各時距實際值落在 80% 區間內的比例為{" "}
              {formatPercent(Math.min(...coverage), 0)}–{formatPercent(Math.max(...coverage), 0)}。<a href={routeToHash({ name: "model" })}>查看模型監控</a>
            </p>
          </>
        }
      >
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
          <p className="muted small planner-threshold">
            超標門檻：AQI &gt; {threshold}（{AUDIENCE[sensitivity]}）
          </p>
        </div>

        <div className="planner-result" aria-live="polite" data-testid="planner-result">
          {best && windowStart && windowEnd ? (
            <>
              {best.risk >= HIGH_RISK && (
                <p className="notice planner-warning" data-testid="planner-warning">
                  未來每個可選的 {hours} 小時時段{best.risk >= 0.995 ? "都預估會超標" : `的平均超標機率都不低於 ${formatPercent(best.risk, 0)}`}，{AUDIENCE[sensitivity]}可考慮改到室內或縮短時間；上面是相對風險最低的時段。
                </p>
              )}
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
          title={`${station.station} AQI：過去 ${HISTORY_SHOWN} 小時與資料時間起算的 24 小時預報`}
          legend={<Legend series={forecastLegend} />}
          summary={(provenance.is_model_estimate ? "實線為每 3 小時模型估算值與時點間插值" : "實線為來源資料") + "、虛線為點預測，陰影為目標覆蓋率 80% 的預測區間；紅線是" + AUDIENCE[sensitivity] + "門檻 " + threshold + (best ? "，綠色區塊是建議時段" : "") + "；最佳時段只比較尚未發生的預報。"}
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
                {availableForecast.length ? (
                  availableForecast.map((f) => (
                    <tr key={f.h} data-forecast-time={f.t}>
                      <th scope="row">{formatHour(f.t)}</th>
                      <td className="num">{formatNumber(f.p10)}</td>
                      <td className="num">{formatNumber(f.p50)}</td>
                      <td className="num">{formatNumber(f.p90)}</td>
                      <td className="num">{formatPercent(exceedanceProbability(f, threshold), 1)}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5}>目前沒有尚未發生的預報時段。</td>
                  </tr>
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
      </Chapter>
    </div>
  );
}

export default function Station(props: Props) {
  const overview = useDataset("overview.json");
  const model = useDataset("model.json");
  const provenance = useDataset("provenance.json");
  // An unknown name must not become the tab title; the page then says the location was not found.
  const missing = overview.status === "ready" && !overview.data.stations.some((s) => s.station === props.station);
  useDocumentTitle(missing ? "找不到這個地點" : props.station);
  return (
    <div className="page">
      <Gate<[Overview, Model, Provenance]> states={[overview, model, provenance]}>{(o, m, p) => <StationView overview={o} model={m} provenance={p} {...props} />}</Gate>
    </div>
  );
}
