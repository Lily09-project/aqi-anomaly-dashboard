import { useDataset, useDocumentTitle } from "../app/hooks";
import { ChartFrame, Legend, MultiLine, type Series } from "../components/charts";
import { ScrollRegion } from "../components/ScrollRegion";
import { Gate } from "../components/States";
import { coverageStatus, skill, upstreamGain } from "../lib/analysis";
import { formatDay, formatNumber, formatPercent, formatSigned } from "../lib/format";
import type { Model } from "../lib/types";

const COVERAGE_LABEL = { calibrated: "已校準", "too-narrow": "區間太窄", "too-wide": "區間偏寬" } as const;
const COVERAGE_TONE = { calibrated: "good", "too-narrow": "bad", "too-wide": "warn" } as const;
const DRIFT_LABEL: Record<string, string> = { stable: "穩定", watch: "留意", alert: "警示", insufficient: "資料不足" };
const DRIFT_TONE: Record<string, string> = { stable: "good", watch: "warn", alert: "bad", insufficient: "info" };
const FEATURE_LABEL: Record<string, string> = {
  aqi_now: "目前 AQI",
  aqi_lag1: "1 小時前 AQI",
  aqi_lag3: "3 小時前 AQI",
  aqi_mean6: "過去 6 小時平均",
  pm25_now: "目前 PM2.5",
  wind_now: "目前風速",
  clim_now: "此刻的典型 AQI",
  clim_target: "目標時刻的典型 AQI",
  upstream_anomaly: "上游地點的異常量",
};

function ModelView({ model }: { model: Model }) {
  const horizons = model.horizons;
  const labels = horizons.map((h) => `${h.h}h`);
  const beatsPersistence = horizons.filter((h) => h.mae < h.persistence_mae).length;
  const beatsClimatology = horizons.filter((h) => h.mae < h.climatology_mae);
  const losesClimatology = horizons.filter((h) => h.mae >= h.climatology_mae).map((h) => h.h);
  const meanCoverage = horizons.reduce((s, h) => s + h.coverage, 0) / Math.max(horizons.length, 1);
  const gains = horizons.map(upstreamGain);
  const shortGain = gains.slice(0, 6).filter((g): g is number => g !== null);
  const avgShortGain = shortGain.length ? shortGain.reduce((a, b) => a + b, 0) / shortGain.length : null;
  const maeSeries: Series[] = [
    { key: "mae", label: "本模型（含上游特徵）", values: horizons.map((h) => h.mae), tone: 1 },
    { key: "persistence", label: "持續性基準（未來和現在一樣）", values: horizons.map((h) => h.persistence_mae), tone: 2 },
    { key: "climatology", label: "氣候值基準（這個時段的典型值）", values: horizons.map((h) => h.climatology_mae), tone: 3 },
    { key: "without", label: "本模型（不含上游特徵）", values: horizons.map((h) => h.mae_without_upstream), tone: 4 },
  ];

  return (
    <div className="stack">
      <header>
        <span className="eyebrow">模型治理</span>
        <h1>模型監控</h1>
        <p className="lede">
          一個預報值不值得相信，要看它在沒看過的資料上表現如何。資料依時間切成訓練（至 {formatDay(model.split.train_end)}）、校準（至{" "}
          {formatDay(model.split.calibration_end)}）與測試（至 {formatDay(model.split.test_end)}）三段，下面所有數字都來自測試期。
        </p>
      </header>

      <section className="kpis" aria-label="摘要">
        <div className="card kpi">
          <span className="stat-label">優於持續性基準的時距</span>
          <span className="stat-value" data-testid="beats-persistence">
            {beatsPersistence}/{horizons.length}
          </span>
          <span className="muted small">1 小時預報的技術分數 {formatPercent(skill(horizons[0]?.mae ?? 0, horizons[0]?.persistence_mae ?? 0), 0)}</span>
        </div>
        <div className="card kpi">
          <span className="stat-label">優於氣候值基準的時距</span>
          <span className="stat-value">
            {beatsClimatology.length}/{horizons.length}
          </span>
          <span className="muted small">
            {losesClimatology.length ? `第 ${losesClimatology.join("、")} 小時沒有贏過「這個時段的典型值」，長時距的預報價值有限。` : "所有時距都贏過典型值。"}
          </span>
        </div>
        <div className="card kpi">
          <span className="stat-label">80% 區間的平均實際覆蓋率</span>
          <span className="stat-value" data-testid="mean-coverage">
            {formatPercent(meanCoverage, 1)}
          </span>
          <span className="muted small">目標 {formatPercent(model.target_coverage, 0)}；略高代表區間保守</span>
        </div>
        <div className="card kpi">
          <span className="stat-label">上游特徵對下游地點的幫助</span>
          <span className="stat-value">{avgShortGain === null ? "—" : formatSigned(avgShortGain * 100, 1) + "%"}</span>
          <span className="muted small">1–6 小時的平均誤差降幅；正值代表誤差較低，負值代表較高</span>
        </div>
      </section>

      <section className="card">
        <ChartFrame
          title="各預報時距的平均絕對誤差（越低越好）"
          summary={`本模型在 ${beatsPersistence} 個時距優於持續性基準，${beatsClimatology.length} 個時距優於氣候值基準。`}
          table={
            <table data-testid="mae-table">
              <thead>
                <tr>
                  <th scope="col">時距</th>
                  {maeSeries.map((s) => (
                    <th scope="col" key={s.key}>
                      {s.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {horizons.map((h) => (
                  <tr key={h.h}>
                    <th scope="row">{h.h} 小時</th>
                    <td className="num">{h.mae.toFixed(2)}</td>
                    <td className="num">{h.persistence_mae.toFixed(2)}</td>
                    <td className="num">{h.climatology_mae.toFixed(2)}</td>
                    <td className="num">{h.mae_without_upstream.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        >
          <MultiLine series={maeSeries} labels={labels} format={(v) => String(v)} yMin={0} />
        </ChartFrame>
        <Legend series={maeSeries} />
      </section>

      <section className="split">
        <div className="card">
          <ChartFrame
            title="80% 預測區間的實際覆蓋率"
            summary={`各時距的實際覆蓋率介於 ${formatPercent(Math.min(...horizons.map((h) => h.coverage)), 0)} 與 ${formatPercent(Math.max(...horizons.map((h) => h.coverage)), 0)}，目標 ${formatPercent(model.target_coverage, 0)}。`}
            table={
              <table data-testid="coverage-table">
                <thead>
                  <tr>
                    <th scope="col">時距</th>
                    <th scope="col">覆蓋率</th>
                    <th scope="col">判定</th>
                    <th scope="col">測試筆數</th>
                  </tr>
                </thead>
                <tbody>
                  {horizons.map((h) => {
                    const status = coverageStatus(h.coverage, model.target_coverage);
                    return (
                      <tr key={h.h}>
                        <th scope="row">{h.h} 小時</th>
                        <td className="num">{formatPercent(h.coverage, 1)}</td>
                        <td>
                          <span className="tag" data-tone={COVERAGE_TONE[status]}>
                            {COVERAGE_LABEL[status]}
                          </span>
                        </td>
                        <td className="num">{h.test_size.toLocaleString("zh-TW")}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            }
          >
            <MultiLine
              series={[{ key: "coverage", label: "實際覆蓋率", values: horizons.map((h) => h.coverage * 100), tone: 1 }]}
              labels={labels}
              reference={{ value: model.target_coverage * 100, label: `目標 ${formatPercent(model.target_coverage, 0)}` }}
              format={(v) => `${v}%`}
              yMin={60}
            />
          </ChartFrame>
        </div>
        <div className="card">
          <ChartFrame
            title="上游特徵讓下游地點誤差下降多少"
            summary={`下游地點（${model.downstream_stations.join("、")}）在 1 小時時距誤差下降 ${formatPercent(gains[0] ?? null, 1)}，24 小時時距為 ${formatPercent(gains.at(-1) ?? null, 1)}。`}
            table={
              <table>
                <thead>
                  <tr>
                    <th scope="col">時距</th>
                    <th scope="col">不含上游</th>
                    <th scope="col">含上游</th>
                    <th scope="col">改善</th>
                  </tr>
                </thead>
                <tbody>
                  {horizons.map((h, i) => (
                    <tr key={h.h}>
                      <th scope="row">{h.h} 小時</th>
                      <td className="num">{formatNumber(h.downstream_mae_without_upstream, 2)}</td>
                      <td className="num">{formatNumber(h.downstream_mae, 2)}</td>
                      <td className="num">{formatPercent(gains[i] ?? null, 1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
          >
            <MultiLine
              series={[{ key: "gain", label: "誤差下降（%）", values: gains.map((g) => (g === null ? null : g * 100)), tone: 1 }]}
              labels={labels}
              reference={{ value: 0, label: "沒有幫助" }}
              format={(v) => `${v}%`}
            />
          </ChartFrame>
          <p className="muted small">比較同一測試期有無上游特徵的誤差；結果反映預測表現差異，不能據此判定污染傳播的因果。</p>
        </div>
      </section>

      <section className="split">
        <div className="card">
          <h2>分布漂移（PM2.5）</h2>
          <p className="muted small">最近 7 天的平均值，相對前 14 天偏移了幾個標準差。超過 0.5 留意、超過 1 警示，代表模型可能需要重新訓練。</p>
          <ScrollRegion label="分布漂移">
            <table data-testid="drift-table">
              <thead>
                <tr>
                  <th scope="col">測站</th>
                  <th scope="col">前 14 天</th>
                  <th scope="col">最近 7 天</th>
                  <th scope="col">偏移（SD）</th>
                  <th scope="col">狀態</th>
                </tr>
              </thead>
              <tbody>
                {model.drift.map((d) => (
                  <tr key={d.station}>
                    <th scope="row">{d.station}</th>
                    <td className="num">{formatNumber(d.reference_mean, 1)}</td>
                    <td className="num">{formatNumber(d.current_mean, 1)}</td>
                    <td className="num">{d.shift_sd === null ? "—" : formatSigned(d.shift_sd, 2)}</td>
                    <td>
                      <span className="tag" data-tone={DRIFT_TONE[d.status] ?? "info"}>
                        {DRIFT_LABEL[d.status] ?? d.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollRegion>
        </div>
        <div className="card">
          <h2>模型輸入</h2>
          <ul>
            {model.features.map((f) => (
              <li key={f}>{FEATURE_LABEL[f] ?? f}</li>
            ))}
          </ul>
          <p className="muted small">每個時距一個 ridge 迴歸（直接多步預測），不把前一步的預測餵回去，所以誤差不會一路累積。</p>
        </div>
      </section>
    </div>
  );
}

export default function ModelPage() {
  useDocumentTitle("模型監控");
  const model = useDataset("model.json");
  return (
    <div className="page">
      <Gate<[Model]> states={[model]}>{(m) => <ModelView model={m} />}</Gate>
    </div>
  );
}
