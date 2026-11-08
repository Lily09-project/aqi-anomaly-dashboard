import { useDataset, useDocumentTitle } from "../app/hooks";
import { Chapter, PageHead } from "../components/Chapter";
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

  const coverages = horizons.map((h) => h.coverage);
  const minCoverage = coverages.length ? Math.min(...coverages) : null;
  const maxCoverage = coverages.length ? Math.max(...coverages) : null;
  const meanStatus = horizons.length ? coverageStatus(meanCoverage, model.target_coverage) : null;
  const drifting = model.drift.filter((d) => d.status === "alert" || d.status === "watch");
  const alerts = model.drift.filter((d) => d.status === "alert");

  return (
    <div className="stack">
      <PageHead kicker="模型治理" title="模型監控">
        <p className="lede">
          一個預報值不值得相信，要看它在沒看過的資料上表現如何。資料依時間切成訓練（至 {formatDay(model.split.train_end)}）、校準（至{" "}
          {formatDay(model.split.calibration_end)}）與測試（至 {formatDay(model.split.test_end)}）三段，下面所有數字都來自測試期。
        </p>
      </PageHead>

      <section className="kpis" aria-label="摘要">
        <div className="kpi">
          <span className="stat-label">優於持續性基準的時距</span>
          <span className="stat-value" data-testid="beats-persistence">
            {beatsPersistence}/{horizons.length}
          </span>
          <span className="muted small">
            1 小時預報的技術分數 {formatPercent(skill(horizons[0]?.mae ?? 0, horizons[0]?.persistence_mae ?? 0), 0)}（相對「維持現狀」的誤差降幅，負值代表誤差較大）
          </span>
        </div>
        <div className="kpi">
          <span className="stat-label">優於氣候值基準的時距</span>
          <span className="stat-value">
            {beatsClimatology.length}/{horizons.length}
          </span>
          <span className="muted small">
            {losesClimatology.length ? `第 ${losesClimatology.join("、")} 小時沒有贏過「這個時段的典型值」，長時距的預報價值有限。` : "所有時距都贏過典型值。"}
          </span>
        </div>
        <div className="kpi">
          <span className="stat-label">80% 區間的平均實際覆蓋率</span>
          <span className="stat-value" data-testid="mean-coverage">
            {formatPercent(meanCoverage, 1)}
          </span>
          <span className="muted small">目標 {formatPercent(model.target_coverage, 0)}；略高代表區間保守</span>
        </div>
        <div className="kpi">
          <span className="stat-label">上游特徵對下游地點的幫助</span>
          <span className="stat-value">{avgShortGain === null ? "—" : formatSigned(avgShortGain * 100, 1) + "%"}</span>
          <span className="muted small">1–6 小時的平均誤差降幅；正值代表誤差較低，負值代表較高</span>
        </div>
      </section>

      <Chapter
        no="01"
        title="誤差：有沒有贏過簡單基準"
        takeaway={
          <>
            本模型在 <strong>{beatsPersistence}/{horizons.length}</strong> 個時距的誤差低於「維持現狀」，<strong>{beatsClimatology.length}/{horizons.length}</strong> 個時距低於「同時段典型值」。
          </>
        }
        howTo={
          <>
            <p>縱軸是平均絕對誤差（MAE，單位 AQI），越低越好；橫軸是往後預報幾小時。</p>
            <p>「維持現狀」假設未來和現在一樣；「典型值」用這個時段的歷史平均。贏不過它們的時距，預報就沒有額外價值。</p>
          </>
        }
      >
        {horizons[0] && beatsPersistence * 2 < horizons.length && (
          <p className="callout" data-testid="persistence-note">
            本模型在 {horizons.length - beatsPersistence}/{horizons.length} 個時距沒有贏過「維持現狀」。這份資料的 AQI 逐時變化很平滑（1 小時後與現在平均只差{" "}
            {formatNumber(horizons[0].persistence_mae, 2)}），維持現狀本身就是很強的基準；這裡的預報較適合用 80% 區間了解不確定性，而不是取代目前數值。
          </p>
        )}
        <div className="card">
          <ChartFrame
            title="各預報時距的平均絕對誤差（AQI，越低越好）"
            legend={<Legend series={maeSeries} />}
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
        </div>
      </Chapter>

      <Chapter
        no="02"
        title="區間：80% 區間可不可靠"
        takeaway={
          meanStatus && minCoverage !== null && maxCoverage !== null ? (
            <>
              各時距的實際覆蓋率介於 {formatPercent(minCoverage, 0)} 與 {formatPercent(maxCoverage, 0)}，平均 {formatPercent(meanCoverage, 1)}，相對目標 {formatPercent(model.target_coverage, 0)}
              判定為<strong>{COVERAGE_LABEL[meanStatus]}</strong>。
            </>
          ) : undefined
        }
        howTo={
          <p>覆蓋率是測試期實際值落在 80% 區間內的比例。低於目標代表區間太窄、太有自信；略高代表區間保守。判定容許低 5 個百分點、高 10 個百分點。</p>
        }
      >
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
              yMin={Math.min(60, ...horizons.map((h) => h.coverage * 100))}
            />
          </ChartFrame>
        </div>
      </Chapter>

      <Chapter
        no="03"
        title="上游特徵有沒有幫助"
        takeaway={
          avgShortGain === null ? (
            <>這份資料沒有可比較的下游地點，無法計算上游特徵的幫助。</>
          ) : (
            <>
              加入上游地點的異常量後，下游地點 1–6 小時的誤差平均{avgShortGain >= 0 ? "下降" : "上升"} <strong>{formatPercent(Math.abs(avgShortGain), 1)}</strong>。
            </>
          )
        }
        howTo={<p>比較同一測試期有無上游特徵的誤差；結果反映預測表現差異，不能據此判定污染傳播的因果。</p>}
      >
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
        </div>
      </Chapter>

      <Chapter
        no="04"
        title="分布漂移與模型輸入"
        takeaway={
          drifting.length ? (
            <>
              {model.drift.length} 個地點中有 <strong>{drifting.length}</strong> 個的 PM2.5 分布出現偏移
              {alerts.length ? `，其中 ${alerts.map((d) => d.station).join("、")} 達警示` : ""}，模型可能需要重新訓練。
            </>
          ) : (
            <>{model.drift.length} 個地點的 PM2.5 分布都沒有明顯偏移。</>
          )
        }
        howTo={
          <>
            <p>最近 7 天的平均值，相對前 14 天偏移了幾個標準差。達 0.5 為留意、達 1 為警示。</p>
            <p>每個時距一個 ridge 迴歸（直接多步預測），不把前一步的預測餵回去，所以誤差不會一路累積。</p>
          </>
        }
      >
        <div className="drift-grid">
          <div className="card">
            <h3 className="card-title">分布漂移（PM2.5）</h3>
            <ScrollRegion label="分布漂移">
              <table data-testid="drift-table">
                <thead>
                  <tr>
                    <th scope="col">地點</th>
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
            <h3 className="card-title">模型輸入</h3>
            <ul className="feature-list">
              {model.features.map((f) => (
                <li key={f}>{FEATURE_LABEL[f] ?? f}</li>
              ))}
            </ul>
          </div>
        </div>
      </Chapter>
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
