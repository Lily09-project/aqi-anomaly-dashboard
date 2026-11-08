import type { ReactNode } from "react";
import { useDataset, useRoute } from "../app/hooks";
import { formatDay } from "../lib/format";
import { routeToHash, type Route } from "../lib/router";
import "./Shell.css";

/** Each page is a chapter of the lab notebook; the number and question help a first-time reader choose. */
const NAV: { route: Route; label: string; no: string; hint: string; match: Route["name"][] }[] = [
  { route: { name: "home" }, label: "空品總覽", no: "00", hint: "現在與未來 24 小時", match: ["home", "station"] },
  { route: { name: "propagation" }, label: "時序關聯", no: "01", hint: "哪裡先變化？", match: ["propagation"] },
  { route: { name: "anomalies" }, label: "異常事件", no: "02", hint: "何時異常偏高？", match: ["anomalies"] },
  { route: { name: "whatif" }, label: "情境模擬", no: "03", hint: "條件改變會怎樣？", match: ["whatif"] },
  { route: { name: "model" }, label: "模型監控", no: "04", hint: "預報值得相信嗎？", match: ["model"] },
  { route: { name: "data" }, label: "資料可信度", no: "05", hint: "資料從哪裡來？", match: ["data"] },
];

export function Shell({ children }: { children: ReactNode }) {
  const [route] = useRoute();
  const provenance = useDataset("provenance.json");
  const simulated = provenance.status === "ready" ? provenance.data.is_simulated : null;
  const modelled = provenance.status === "ready" && provenance.data.is_model_estimate === true;

  return (
    <>
      <a className="skip-link" href="#main" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus(); }}>
        跳到主要內容
      </a>
      <header className="site-header">
        <div className="site-header-inner">
          <a className="brand" href={routeToHash({ name: "home" })}>
            <span className="brand-mark" aria-hidden="true">AIR</span>
            <span className="brand-text">
              <strong>Taiwan Air Lab</strong>
              <span>台灣空氣實驗室</span>
            </span>
          </a>
          <nav aria-label="主要頁面" className="site-nav">
            <ul>
              {NAV.map((item) => (
                <li key={item.label}>
                  <a href={routeToHash(item.route)} aria-current={item.match.includes(route.name) ? "page" : undefined}>
                    <span className="nav-no" aria-hidden="true">{item.no}</span>
                    <span className="nav-label">{item.label}</span>
                    <span className="nav-hint" aria-hidden="true">{item.hint}</span>
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <div className="site-tools">
            {simulated !== null && (
              <a className="data-badge" href={routeToHash({ name: "data" })} data-simulated={simulated} data-testid="data-badge">
                {modelled ? "CAMS 模型估算" : simulated ? "測試資料" : "資料快照"}
              </a>
            )}
          </div>
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        {children}
      </main>
      <footer className="site-footer">
        <div className="site-footer-inner">
          <p>
            {provenance.status === "ready" && (
              <>
                資料期間 {formatDay(provenance.data.range.start)} 至 {formatDay(provenance.data.range.end)}
                {modelled
                  ? "（CAMS 模型原生約每 " + (provenance.data.native_temporal_resolution_hours ?? 3) + " 小時一筆、約 " + (provenance.data.spatial_resolution_km ?? 45) + " 公里網格；非測站實測）"
                  : provenance.data.is_simulated ? "（可重現的測試資料）" : "（公開資料快照）"}。
              </>
            )}
            本站不是即時空品服務，也不是官方預報；所有預測與機率皆為分析示範，健康決策請以環境部即時資訊為準。
          </p>
          <p className="muted">
            <a href={routeToHash({ name: "data" })}>方法、限制與資料完整性</a>
          </p>
        </div>
      </footer>
    </>
  );
}
