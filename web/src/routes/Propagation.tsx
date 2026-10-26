import { useEffect, useState } from "react";
import { useDataset, useDocumentTitle, useRoute } from "../app/hooks";
import { ArrivalStrips, ChartFrame, TaiwanMap } from "../components/charts";
import { ScrollRegion } from "../components/ScrollRegion";
import { Gate } from "../components/States";
import { categoryOf } from "../lib/air";
import { episodeFrame, lagAgreement, peakFrames } from "../lib/analysis";
import { formatHour, formatNumber } from "../lib/format";
import type { Overview, Propagation } from "../lib/types";
import "./Propagation.css";

const shortName = (name: string) => name.replace(/(?:測站|網格)$/, "");

function Replay({ overview, propagation, initialFrame }: { overview: Overview; propagation: Propagation; initialFrame: number }) {
  const [, navigate] = useRoute();
  const episode = propagation.episode;
  const last = Math.max(episode.times.length - 1, 0);
  const [frame, setFrame] = useState(Math.min(initialFrame, last));
  const [playing, setPlaying] = useState(false);
  const isPlaying = playing && frame < last;

  useEffect(() => {
    if (!isPlaying) return;
    const id = window.setInterval(() => setFrame((f) => Math.min(f + 1, last)), 450);
    return () => window.clearInterval(id);
  }, [isPlaying, last]);

  useEffect(() => {
    navigate({ name: "propagation", frame }, { replace: true });
  }, [frame, navigate]);

  const values = episodeFrame(episode, frame);
  const peaks = peakFrames(episode);
  const truth = propagation.ground_truth ?? {};
  const hasTruth = Object.keys(truth).length > 0;
  // With ground truth, order rows by the known transport lag; otherwise by observed peak time.
  const plume = hasTruth
    ? peaks.filter((p) => p.station in truth).sort((a, b) => (truth[a.station] ?? 0) - (truth[b.station] ?? 0))
    : peaks;
  const rows = plume.map((p) => ({ key: p.station, label: shortName(p.station), values: episode.aqi[p.station] ?? [], peak: p.frame }));
  const time = episode.times[frame] ?? "";

  return (
    <section className="card replay" aria-labelledby="replay-title">
      <h2 id="replay-title">資料時序回放</h2>
      <p className="muted">
        {formatHour(episode.start)} 至 {formatHour(episode.end)}。各地點依峰值時間排序；模型原始資料每 3 小時一次，中間時點為插值，不代表污染實際移動。
      </p>
      <div className="replay-controls" role="group" aria-label="重播控制">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => {
            if (isPlaying) setPlaying(false);
            else {
              if (frame >= last) setFrame(0);
              setPlaying(true);
            }
          }}
          aria-pressed={isPlaying}
        >
          {isPlaying ? "暫停" : "播放"}
        </button>
        <button type="button" className="btn" onClick={() => { setPlaying(false); setFrame((f) => Math.max(f - 1, 0)); }} disabled={frame === 0}>
          上一小時
        </button>
        <button type="button" className="btn" onClick={() => { setPlaying(false); setFrame((f) => Math.min(f + 1, last)); }} disabled={frame === last}>
          下一小時
        </button>
        <label className="field replay-slider">
          <span className="label">
            時間 <output data-testid="replay-time">{formatHour(time)}</output>
          </span>
          <input
            type="range"
            min={0}
            max={last}
            step={1}
            value={frame}
            onChange={(e) => {
              setPlaying(false);
              setFrame(Number(e.target.value));
            }}
            aria-valuetext={formatHour(time)}
          />
        </label>
      </div>
      <div className="split">
        <ChartFrame
          title={`${formatHour(time)} 各地點 AQI`}
          summary={overview.stations.map((s) => `${s.station} ${formatNumber(values[s.station] ?? null)}`).join("、")}
          table={
            <table>
              <thead>
                <tr>
                  <th scope="col">地點</th>
                  <th scope="col">AQI</th>
                </tr>
              </thead>
              <tbody>
                {overview.stations.map((s) => (
                  <tr key={s.station}>
                    <th scope="row">{s.station}</th>
                    <td className="num">{formatNumber(values[s.station] ?? null)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        >
          <TaiwanMap
            stations={overview.stations.map((s) => {
              const v = values[s.station] ?? null;
              return {
                name: s.station,
                lon: s.longitude,
                lat: s.latitude,
                category: categoryOf(v, overview.categories)?.key ?? null,
                label: `${shortName(s.station)} ${formatNumber(v)}`,
              };
            })}
          />
        </ChartFrame>
        <ChartFrame
          title="各地點 AQI 時序（依峰值時間排序）"
          summary={plume.map((p) => `${p.station} 在 ${formatHour(episode.times[p.frame] ?? "")} 達高峰 ${formatNumber(p.aqi)}`).join("；")}
          table={
            <table data-testid="arrival-table">
              <thead>
                <tr>
                  <th scope="col">地點</th>
                  <th scope="col">高峰時間</th>
                  <th scope="col">高峰 AQI</th>
                </tr>
              </thead>
              <tbody>
                {plume.map((p) => (
                  <tr key={p.station}>
                    <th scope="row">{p.station}</th>
                    <td>{formatHour(episode.times[p.frame] ?? "")}</td>
                    <td className="num">{formatNumber(p.aqi)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          }
        >
          <ArrivalStrips rows={rows} labels={episode.times.map(formatHour)} frame={frame} />
        </ChartFrame>
      </div>
    </section>
  );
}

function PropagationView({ overview, propagation, frame }: { overview: Overview; propagation: Propagation; frame: number }) {
  const agreement = lagAgreement(propagation.links);
  const hasTruth = propagation.ground_truth !== null;
  const linked = new Set(propagation.links.flatMap((l) => [l.upstream, l.downstream]));
  const isolated = overview.stations.filter((s) => !linked.has(s.station));
  const chain = Object.entries(propagation.nearest_upstream).map(([downstream, u]) => ({
    from: u.upstream,
    to: downstream,
    label: `${u.lag_hours}h`,
  }));
  const links = [...propagation.links].sort((a, b) => a.lag_hours - b.lag_hours || b.r - a.r);

  return (
    <div className="stack">
      <header>
        <span className="eyebrow">空間分析</span>
        <h1>空品時序關聯</h1>
        <p className="lede">
          比較扣除時段基準後的 PM2.5 變化順序。模型原始資料每 3 小時一次，中間時點為插值；相關不代表污染路徑或預警。
        </p>
      </header>

      <section className="kpis" aria-label="摘要">
        <div className="card kpi">
          <span className="stat-label">顯著的領先關係</span>
          <span className="stat-value">{propagation.links.length}</span>
          <span className="muted small">落後 1–{propagation.max_lag} 小時、相關係數 ≥ {propagation.min_correlation}，且優於同時相關</span>
        </div>
        {hasTruth && (
          <div className="card kpi">
            <span className="stat-label">已知延遲比對</span>
            <span className="stat-value" data-testid="lag-agreement">
              {agreement.matched}/{agreement.total}
            </span>
            <span className="muted small">偵測延遲落在測試值 ±1 小時內的關係數</span>
          </div>
        )}
        <div className="card kpi">
          <span className="stat-label">未形成顯著關聯的地點</span>
          <span className="stat-value" data-testid="isolated">
            {isolated.length ? isolated.map((s) => shortName(s.station)).join("、") : "無"}
          </span>
          <span className="muted small">部分地點未達關聯門檻</span>
        </div>
      </section>

      <section className="split">
        <div className="card">
          <ChartFrame
            title="較早關聯地點與時間差"
            summary={chain.map((c) => `${c.from} 的變化早於 ${c.to} ${c.label}`).join("、")}
            table={
              <table>
                <thead>
                  <tr>
                    <th scope="col">較晚變化地點</th>
                    <th scope="col">較早關聯地點</th>
                    <th scope="col">延遲（小時）</th>
                  </tr>
                </thead>
                <tbody>
                  {chain.map((c) => (
                    <tr key={c.to}>
                      <th scope="row">{c.to}</th>
                      <td>{c.from}</td>
                      <td className="num">{c.label.replace("h", "")}</td>
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
                category: null,
                label: shortName(s.station),
              }))}
              links={chain}
            />
          </ChartFrame>
        </div>
        <div className="card">
          <h2>所有顯著關係</h2>
          <ScrollRegion label="地點領先落後關係">
            <table data-testid="links-table">
              <thead>
                <tr>
                  <th scope="col">較早變化 → 較晚變化</th>
                  <th scope="col">偵測延遲</th>
                  {hasTruth && <th scope="col">測試延遲</th>}
                  <th scope="col">r（落後）</th>
                  <th scope="col">r（同時）</th>
                </tr>
              </thead>
              <tbody>
                {links.map((l) => {
                  const ok = l.truth_lag !== null && Math.abs(l.lag_hours - l.truth_lag) <= 1;
                  return (
                    <tr key={`${l.upstream}-${l.downstream}`}>
                      <th scope="row">
                        {shortName(l.upstream)} → {shortName(l.downstream)}
                      </th>
                      <td className="num">{l.lag_hours} h</td>
                      {hasTruth && (
                        <td className="num">
                          {l.truth_lag === null ? "—" : `${l.truth_lag} h`}{" "}
                          {l.truth_lag !== null && (
                            <span className="tag" data-tone={ok ? "good" : "bad"}>
                              {ok ? "吻合" : "誤差 > 1h"}
                            </span>
                          )}
                        </td>
                      )}
                      <td className="num">{l.r.toFixed(2)}</td>
                      <td className="num">{l.r_synchronous.toFixed(2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollRegion>
          {hasTruth && <p className="muted small">測試延遲來自已知答案 fixture，僅供驗證分析方法。</p>}
        </div>
      </section>

      <Replay overview={overview} propagation={propagation} initialFrame={frame} />
    </div>
  );
}

export default function PropagationPage({ frame }: { frame?: number }) {
  useDocumentTitle("空品時序關聯");
  const overview = useDataset("overview.json");
  const propagation = useDataset("propagation.json");
  return (
    <div className="page">
      <Gate<[Overview, Propagation]> states={[overview, propagation]}>
        {(o, p) => <PropagationView overview={o} propagation={p} frame={frame ?? 0} />}
      </Gate>
    </div>
  );
}
