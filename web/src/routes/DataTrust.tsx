import { useContext, useEffect, useState } from "react";
import { LoaderContext, useDataset, useDocumentTitle } from "../app/hooks";
import { IntegrityError } from "../lib/data";
import { Chapter, PageHead } from "../components/Chapter";
import { ScrollRegion } from "../components/ScrollRegion";
import { Gate } from "../components/States";
import { formatDay, formatPercent } from "../lib/format";
import type { Anomalies, DataFiles, Manifest, Propagation, Provenance } from "../lib/types";
import "./DataTrust.css";

const FILES: (keyof DataFiles)[] = ["overview.json", "propagation.json", "anomalies.json", "whatif.json", "model.json", "provenance.json"];

/** "failed" is a SHA-256 mismatch; "unavailable" means the file or manifest could not be fetched at all. */
type Check = { file: string; status: "pending" | "ok" | "failed" | "unavailable"; hash?: string };

function useIntegrityChecks(): { manifest: Manifest | null; checks: Check[] } {
  const loader = useContext(LoaderContext);
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [checks, setChecks] = useState<Check[]>(FILES.map((file) => ({ file, status: "pending" })));
  useEffect(() => {
    if (!loader) return;
    let alive = true;
    // A manifest failure surfaces through every file check below; do not leave it unhandled.
    loader.manifest().then(
      (m) => alive && setManifest(m),
      () => undefined,
    );
    FILES.forEach((file, i) => {
      loader.load(file).then(
        () => alive && setChecks((prev) => prev.map((c, j) => (j === i ? { ...c, status: "ok" } : c))),
        (error: unknown) =>
          alive && setChecks((prev) => prev.map((c, j) => (j === i ? { ...c, status: error instanceof IntegrityError ? "failed" : "unavailable" } : c))),
      );
    });
    return () => {
      alive = false;
    };
  }, [loader]);
  return { manifest, checks: checks.map((c) => ({ ...c, hash: manifest?.files[c.file] })) };
}

function Trust({ provenance, anomalies, propagation }: { provenance: Provenance; anomalies: Anomalies; propagation: Propagation }) {
  const { manifest, checks } = useIntegrityChecks();
  const passed = checks.filter((c) => c.status === "ok").length;
  const pending = checks.filter((c) => c.status === "pending").length;
  const truth = propagation.ground_truth;
  const v = anomalies.validation;
  return (
    <div className="stack">
      <PageHead kicker="資料工程" title="資料可信度">
        <p className="lede">
          {provenance.is_simulated
            ? "展示站使用可重現的合成資料：每次重跑都得到位元組完全相同的結果，而且我們知道「正確答案」，所以能檢查每個分析方法是否真的找得到它。"
            : provenance.is_model_estimate
              ? "資料來自免註冊 Open-Meteo API 的 CAMS Global 模型估算；以下列出模型格點、解析度與檔案指紋。不是測站實測。"
              : "這份資料來自環境部開放資料的快照，以下是它的來源與指紋。"}
        </p>
      </PageHead>

      <section className="kpis" aria-label="摘要">
        <div className="kpi">
          <span className="stat-label">資料來源</span>
          <p className="stat-value stat-text" data-testid="data-source">
            {provenance.is_model_estimate ? "Open-Meteo · CAMS Global" : provenance.is_simulated ? "測試資料" : provenance.data_source}
          </p>
          <span className="muted small">
            {provenance.is_model_estimate ? provenance.model_name : provenance.is_simulated ? "測試種子 " + provenance.seed : provenance.provider ?? "—"}
          </span>
        </div>
        <div className="kpi">
          <span className="stat-label">涵蓋範圍</span>
          <p className="stat-value">{provenance.stations} {provenance.is_model_estimate ? "個模型格點" : "站"}</p>
          <span className="muted small">
            {formatDay(provenance.range.start)} 至 {formatDay(provenance.range.end)} · {provenance.rows.toLocaleString("zh-TW")} 筆{provenance.is_model_estimate ? " API 逐時輸出（底層模型原生約每 " + (provenance.native_temporal_resolution_hours ?? 3) + " 小時）" : "逐時資料"} · 完整度{" "}
            {formatPercent(provenance.completeness, 2)}
          </span>
        </div>
        <div className="kpi">
          <span className="stat-label">瀏覽器端完整性驗證</span>
          <p className="stat-value" data-testid="integrity-summary">
            {passed}/{checks.length}
          </p>
          <span className="muted small">以 Web Crypto 重新計算 SHA-256 並與 manifest 比對</span>
        </div>
      </section>

      <Chapter
        no="01"
        title="完整性檢查"
        takeaway={
          pending > 0 ? (
            <>正在以 Web Crypto 重新計算 {checks.length} 個檔案的 SHA-256…</>
          ) : passed === checks.length ? (
            <>
              {checks.length} 個資料檔全部與 manifest 的 SHA-256 <strong>相符</strong>：你看到的數字就是發布時的檔案。
            </>
          ) : (
            <>
              {checks.length} 個資料檔中有 <strong>{checks.length - passed}</strong> 個沒有通過驗證，網站不會用這些檔案計算。
            </>
          )
        }
        howTo={<p>每個檔案在瀏覽器裡重新計算 SHA-256，再與建置時寫入 manifest 的指紋比對；任何一個位元組不同都會顯示「不符」。</p>}
      >
        <div className="card">
        <ScrollRegion label="完整性檢查結果">
          <table data-testid="integrity-table">
            <thead>
              <tr>
                <th scope="col">檔案</th>
                <th scope="col">狀態</th>
                <th scope="col">SHA-256（schema {manifest?.schema_version ?? "—"}）</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((c) => (
                <tr key={c.file}>
                  <th scope="row" className="mono">
                    {c.file}
                  </th>
                  <td>
                    <span className={`badge check-${c.status === "unavailable" ? "failed" : c.status}`}>
                      {c.status === "ok" ? "✓ 相符" : c.status === "failed" ? "✕ 不符" : c.status === "unavailable" ? "✕ 無法載入" : "驗證中"}
                    </span>
                  </td>
                  <td className="mono hash">{c.hash ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollRegion>
        <dl className="fingerprints">
          <dt>輸入資料 SHA-256</dt>
          <dd className="mono" data-testid="input-sha">
            {provenance.input_sha256 ?? "—"}
          </dd>
          <dt>資料結構 SHA-256</dt>
          <dd className="mono">{provenance.schema_sha256 ?? "—"}</dd>
        </dl>
        </div>
      </Chapter>

      {provenance.is_simulated && (
        <Chapter no="02" title="已知答案與驗證結果">
          <div className="card">
          <p>
            合成資料刻意放進兩種可驗證的結構，分析方法事先不知道答案；答案只用來評分。注入事件清單在 <code>{provenance.injected_events_file ?? "—"}</code>。
          </p>
          <div className="grid grid-2">
            <div>
              <h3>西部污染團的傳播延遲</h3>
              {truth ? (
                <ScrollRegion label="注入的傳播延遲">
                  <table data-testid="truth-table">
                    <thead>
                      <tr>
                        <th scope="col">測站</th>
                        <th scope="col">相對源頭的延遲</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(truth)
                        .sort((a, b) => a[1] - b[1])
                        .map(([station, lag]) => (
                          <tr key={station}>
                            <th scope="row">{station}</th>
                            <td className="num">{lag} 小時</td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </ScrollRegion>
              ) : (
                <p className="muted">無</p>
              )}
              <p className="muted small">宜蘭與花蓮刻意不受污染團影響，用來檢查方法不會「看到不存在的關係」。</p>
            </div>
            <div>
              <h3>注入的局部污染事件</h3>
              {v ? (
                <ul>
                  <li>注入 {v.injected_events} 個事件，偵測到 {formatPercent(v.recall, 0)}。</li>
                  <li>
                    被判為局部的 {v.local_events} 個事件中，{formatPercent(v.local_precision, 0)} 確實是注入事件。
                  </li>
                  <li>{v.injected_labelled_regional} 個注入事件剛好與區域污染團同時發生，被歸為區域事件——這是方法的已知限制。</li>
                </ul>
              ) : (
                <p className="muted">無</p>
              )}
              <p className="muted small">偵測門檻：穩健 z ≥ {anomalies.threshold}；區域判定窗口 ±{anomalies.regional_window_hours} 小時（等於偵測到的最大傳播延遲）。</p>
            </div>
          </div>
          </div>
        </Chapter>
      )}

      <Chapter no={provenance.is_simulated ? "03" : "02"} title="方法與限制" className="method">
        <div className="card method-card">
        <h3>AQI 標準</h3>
        <p>{provenance.is_model_estimate ? "採用 API 提供的美國 EPA AQI 與 PM2.5、PM10、臭氧模型濃度；臭氧單位為 " + (provenance.ozone_unit ?? "μg/m³") + "。數值與環境部測站公告不可直接視為相同。" : "依環境部 PM2.5、PM10、臭氧分段濃度換算子指標並取最大值；以逐時濃度代替官方移動平均，數值可能與公告不同。"}</p>
        <h3>機率預報</h3>
        <p>
          每個預報時距（1–24 小時）各一個 ridge 迴歸（直接多步預測），預報值即 P50；以時間順序切出的校準期絕對殘差第 80 百分位作為 80% 區間的半寬（分割式保形預測），在測試期檢查實際覆蓋率。
        </p>
        <h3>時序關聯</h3>
        <p>對各地點的 PM2.5 扣除「地點 × 時段」的典型值後，計算 1–{propagation.max_lag} 小時的落後互相關。這只呈現資料的時序相關，不能證明污染傳播或因果。</p>
        <h3>異常歸因</h3>
        <p>以每個地點、每個時段的中位數與 MAD 計算穩健 z 分數，連續超過門檻的時段合併為事件；以高峰時各因子的 z 分數排序作為解釋，並以同一組 z 分數找出最相似的歷史事件。</p>
        <h3>不應該怎麼用</h3>
        <ul>
          <li>{provenance.is_model_estimate ? "模型格點不是地面測站，解析度約 45 公里；CAMS 原生約 3 小時，API 逐時輸出含插值。健康決策請查環境部即時資訊。" : "不是即時監測，也不是官方預報；健康決策請以環境部即時資訊為準。"}</li>
          <li>情境模擬是條件相關的線性模型，不代表因果；調整滑桿不會真的改變大氣。</li>
          <li>合成資料只用於測試與 PR 預覽；正式頁面不以合成數據替代上游來源。</li>
        </ul>
        </div>
      </Chapter>

      <Chapter no={provenance.is_simulated ? "04" : "03"} title="資料來源與重現方式">
        <div className="card">
        <ul className="sources">
          {provenance.sources.map((s) => (
            <li key={s.url}>
              <a href={s.url} target="_blank" rel="noopener noreferrer">
                {s.label}
                <span className="visually-hidden">（在新分頁開啟）</span>
              </a>
            </li>
          ))}
        </ul>
        <p>
          <code>python run_all.py --mode sample</code> 只產生測試資料；正式網站僅在公開 API 來源與檔案雜湊通過驗證後發布。
        </p>
        </div>
      </Chapter>
    </div>
  );
}

export default function DataTrust() {
  useDocumentTitle("資料可信度");
  const provenance = useDataset("provenance.json");
  const anomalies = useDataset("anomalies.json");
  const propagation = useDataset("propagation.json");
  return (
    <div className="page">
      <Gate<[Provenance, Anomalies, Propagation]> states={[provenance, anomalies, propagation]}>
        {(p, a, g) => <Trust provenance={p} anomalies={a} propagation={g} />}
      </Gate>
    </div>
  );
}
