import { useEffect, useState } from "react";
import { useDataset, useDocumentTitle, usePrefersReducedMotion, useRoute } from "../app/hooks";
import { ArrivalStrips, ChartFrame, TaiwanMap } from "../components/charts";
import { ScrollRegion } from "../components/ScrollRegion";
import { Gate } from "../components/States";
import { categoryOf } from "../lib/air";
import { episodeFrame, lagAgreement, peakFrames } from "../lib/analysis";
import { formatHour, formatNumber } from "../lib/format";
import type { Overview, Propagation } from "../lib/types";
import "./Propagation.css";

const shortName = (name: string) => name.replace(/測站$/, "");

function Replay({ overview, propagation, initialFrame }: { overview: Overview; propagation: Propagation; initialFrame: number }) {
  const [, navigate] = useRoute();
  const reducedMotion = usePrefersReducedMotion();
  const episode = propagation.episode;
  const last = Math.max(episode.times.length - 1, 0);
  const [frame, setFrame] = useState(Math.min(initialFrame, last));
  const [playing, setPlaying] = useState(false);
  const isPlaying = playing && frame < last;

  useEffect(() => {
    if (!isPlaying) return;
    const id = window.setInterval(() => setFrame((f) => Math.min(f + 1, last)), reducedMotion ? 1200 : 450);
    return () => window.clearInterval(id);
  }, [isPlaying, last, reducedMotion]);

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
      <h2 id="replay-title">事件重播：污染團怎麼走</h2>
      <p className="muted">
        {formatHour(episode.start)} 至 {formatHour(episode.end)}，傳播訊號最強的一段。每一列是一個測站，由上游排到下游；高峰（橘點）一列一列往右移，就是污染團抵達的順序。
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
      {reducedMotion && <p className="muted small">已偵測到「減少動態效果」設定：播放速度放慢且不使用轉場動畫。</p>}
      <div className="split">
        <ChartFrame
          title={`${formatHour(time)} 各測站 AQI`}
          summary={overview.stations.map((s) => `${s.station} ${formatNumber(values[s.station] ?? null)}`).join("、")}
          table={
            <table>
              <thead>
                <tr>
                  <th scope="col">測站</th>
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
          title="各測站 AQI 隨時間變化（上游 → 下游）"
          summary={plume.map((p) => `${p.station} 在 ${formatHour(episode.times[p.frame] ?? "")} 達高峰 ${formatNumber(p.aqi)}`).join("；")}
          table={
            <table data-testid="arrival-table">
              <thead>
                <tr>
                  <th scope="col">測站</th>
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
        <h1>污染傳播追蹤</h1>
        <p className="lede">
          把每個測站的 PM2.5 先扣掉「每天這個時段本來就會有的量」，再看哪個測站的變化固定比另一個早幾小時出現。領先的那一站，就是下游的預警哨。
        </p>
      </header>

      <section className="kpis" aria-label="摘要">
        <div className="card kpi">
          <span className="stat-label">顯著的領先關係</span>
          <span className="stat-value">{propagation.links.length}</span>
          <span className="muted small">落後 1–{propagation.max_lag} 小時、相關係數 ≥ {propagation.min_correlation}，且優於同時相關</span>
        </div>
        <div className="card kpi">
          <span className="stat-label">與注入的真實延遲比對</span>
          <span className="stat-value" data-testid="lag-agreement">
            {agreement.matched}/{agreement.total}
          </span>
          <span className="muted small">偵測延遲落在真實值 ±1 小時內的關係數</span>
        </div>
        <div className="card kpi">
          <span className="stat-label">沒有上游關係的測站</span>
          <span className="stat-value" data-testid="isolated">
            {isolated.length ? isolated.map((s) => shortName(s.station)).join("、") : "無"}
          </span>
          <span className="muted small">中央山脈另一側不受西部污染團影響，沒有被誤判為相關</span>
        </div>
      </section>

      <section className="split">
        <div className="card">
          <ChartFrame
            title="最近上游與延遲時間"
            summary={chain.map((c) => `${c.from} 領先 ${c.to} ${c.label}`).join("、")}
            table={
              <table>
                <thead>
                  <tr>
                    <th scope="col">下游測站</th>
                    <th scope="col">最近上游</th>
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
          <ScrollRegion label="測站領先落後關係">
            <table data-testid="links-table">
              <thead>
                <tr>
                  <th scope="col">上游 → 下游</th>
                  <th scope="col">偵測延遲</th>
                  <th scope="col">真實延遲</th>
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
                      <td className="num">
                        {l.truth_lag === null ? "—" : `${l.truth_lag} h`}{" "}
                        {l.truth_lag !== null && (
                          <span className="tag" data-tone={ok ? "good" : "bad"}>
                            {ok ? "吻合" : "誤差 > 1h"}
                          </span>
                        )}
                      </td>
                      <td className="num">{l.r.toFixed(2)}</td>
                      <td className="num">{l.r_synchronous.toFixed(2)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollRegion>
          <p className="muted small">「真實延遲」來自合成資料產生器：兩站相對污染源的延遲差。真實資料沒有這個答案，屆時這一欄會顯示「—」。</p>
        </div>
      </section>

      <Replay overview={overview} propagation={propagation} initialFrame={frame} />
    </div>
  );
}

export default function PropagationPage({ frame }: { frame?: number }) {
  useDocumentTitle("污染傳播追蹤");
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
