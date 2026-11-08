import { useState } from "react";
import { useDataset, useDocumentTitle } from "../app/hooks";
import { Chapter, PageHead } from "../components/Chapter";
import { ChartFrame, DivergingBars, MultiLine } from "../components/charts";
import { Gate } from "../components/States";
import { categoryOf, defaultInputs, predictWhatIf, whatIfContributions } from "../lib/air";
import { formatNumber, formatSigned } from "../lib/format";
import type { Overview, WhatIf } from "../lib/types";
import "./WhatIf.css";

const SWEEP_POINTS = 25;

/** A station's latest reading, clamped to the slider ranges the model was trained on. */
function stationInputs(model: WhatIf, overview: Overview, name: string): Record<string, number> | null {
  const s = overview.stations.find((st) => st.station === name);
  if (!s) return null;
  const raw: Record<string, number> = {
    aqi_now: s.aqi,
    pm25_now: s.pm25,
    pm10_now: s.pm10,
    o3_now: s.o3,
    wind_now: s.wind_speed,
    hour: Number(overview.latest.slice(11, 13)),
  };
  return Object.fromEntries(model.inputs.map((i) => [i.key, Math.min(Math.max(raw[i.key] ?? i.default, i.min), i.max)]));
}

function Simulator({ model, overview }: { model: WhatIf; overview: Overview }) {
  const [inputs, setInputs] = useState<Record<string, number>>(() => defaultInputs(model));
  const [sweepKey, setSweepKey] = useState("wind_now");
  const [preset, setPreset] = useState("");
  const prediction = predictWhatIf(model, inputs);
  const low = Math.max(prediction + model.residual_p10, 0);
  const high = Math.max(prediction + model.residual_p90, 0);
  const labels = Object.fromEntries(model.inputs.map((i) => [i.key, i.label]));
  const contributions = whatIfContributions(model, inputs);
  // Largest push in each direction, for a one-line reading of the bar chart.
  const strongestUp = contributions.reduce<(typeof contributions)[number] | null>((top, c) => (c.value >= 0.05 && (!top || c.value > top.value) ? c : top), null);
  const strongestDown = contributions.reduce<(typeof contributions)[number] | null>((top, c) => (c.value <= -0.05 && (!top || c.value < top.value) ? c : top), null);
  const sweepInput = model.inputs.find((i) => i.key === sweepKey) ?? model.inputs[0];
  const sweep = sweepInput
    ? Array.from({ length: SWEEP_POINTS }, (_, i) => {
        const raw = sweepInput.min + ((sweepInput.max - sweepInput.min) * i) / (SWEEP_POINTS - 1);
        const value = sweepInput.key === "hour" ? Math.round(raw) : raw;
        return { value, aqi: predictWhatIf(model, { ...inputs, [sweepInput.key]: value }) };
      })
    : [];
  const current = sweepInput ? inputs[sweepInput.key] ?? sweepInput.default : 0;
  const markerIndex = sweepInput ? ((current - sweepInput.min) / Math.max(sweepInput.max - sweepInput.min, 1e-9)) * (SWEEP_POINTS - 1) : 0;
  const decimals = (key: string) => (key === "hour" ? 0 : 1);

  const resultCategory = categoryOf(prediction, overview.categories);
  const sweepLow = sweep[0]?.aqi;
  const sweepHigh = sweep.at(-1)?.aqi;

  return (
    <div className="whatif-layout">
      <section className="card whatif-inputs" aria-labelledby="inputs-title">
        <div className="whatif-live" aria-hidden="true" data-category={resultCategory?.key ?? "none"}>
          <span>下一小時預測</span>
          <strong>{formatNumber(prediction)}</strong>
          <span>
            區間 {formatNumber(low)}–{formatNumber(high)}
          </span>
        </div>
        <h2 id="inputs-title">設定條件</h2>
        <label className="field">
          <span className="label">從地點目前狀態載入</span>
          <select
            className="input"
            value={preset}
            onChange={(e) => {
              setPreset(e.target.value);
              const loaded = stationInputs(model, overview, e.target.value);
              if (loaded) setInputs(loaded);
            }}
          >
            <option value="">自訂</option>
            {overview.stations.map((s) => (
              <option key={s.station} value={s.station}>
                {s.station}
              </option>
            ))}
          </select>
        </label>
        {model.inputs.map((input) => {
          const value = inputs[input.key] ?? input.default;
          const id = `whatif-${input.key}`;
          return (
            <div className="slider" key={input.key}>
              <label htmlFor={id}>
                {input.label}
                <output htmlFor={id} data-testid={`value-${input.key}`}>
                  {formatNumber(value, decimals(input.key))} {input.unit}
                </output>
              </label>
              <input
                id={id}
                type="range"
                min={input.min}
                max={input.max}
                step={input.key === "hour" ? 1 : 0.1}
                value={value}
                onChange={(e) => {
                  setPreset("");
                  setInputs((prev) => ({ ...prev, [input.key]: Number(e.target.value) }));
                }}
                aria-valuetext={`${formatNumber(value, decimals(input.key))} ${input.unit}`.trim()}
              />
              <span className="slider-range muted small" aria-hidden="true">
                <span>{input.min}</span>
                <span>{input.max}</span>
              </span>
            </div>
          );
        })}
        <button
          type="button"
          className="btn"
          onClick={() => {
            setPreset("");
            setInputs(defaultInputs(model));
          }}
        >
          重設為典型值
        </button>
        <p className="muted small">滑桿範圍涵蓋訓練資料的 1%–99% 區間；模型未見過的範圍不提供預測。</p>
      </section>

      <div className="whatif-output">
        <section className="whatif-result" aria-live="polite" aria-labelledby="result-title" data-category={resultCategory?.key ?? "none"}>
          <h2 id="result-title">下一小時 AQI 預測</h2>
          <p className="aqi-big" data-testid="whatif-prediction">
            {formatNumber(prediction)}
          </p>
          <p className="whatif-result-cat">{resultCategory?.label ?? "無資料"}</p>
          <p>
            80% 預測區間 <strong data-testid="whatif-interval">{formatNumber(low)}–{formatNumber(high)}</strong>
          </p>
          <p className="small whatif-result-note">
            區間寬度來自 {model.calibration_size.toLocaleString("zh-TW")} 筆保留校準資料的殘差分位數；模型在你的瀏覽器裡計算，與 Python 版本的結果一致（差異 &lt; 10⁻⁶）。
          </p>
        </section>

        <Chapter
          no="01"
          title="每個條件把預測推高或拉低多少"
          takeaway={
            strongestUp || strongestDown ? (
              <span data-testid="whatif-takeaway">
                {strongestUp && (
                  <>
                    目前最推高預測的是 <strong>{labels[strongestUp.key] ?? strongestUp.key}</strong>（{formatSigned(strongestUp.value, 1)} AQI）
                  </>
                )}
                {strongestUp && strongestDown && "；"}
                {strongestDown && (
                  <>
                    最拉低的是 <strong>{labels[strongestDown.key] ?? strongestDown.key}</strong>（{formatSigned(strongestDown.value, 1)} AQI）
                  </>
                )}
                。
              </span>
            ) : (
              "目前每個條件都接近訓練資料的平均狀態，沒有明顯推高或拉低預測的條件。"
            )
          }
          liveTakeaway
        >
          <ChartFrame
            title="各條件相對平均情況的貢獻（AQI）"
            summary={contributions.map((c) => `${labels[c.key] ?? c.key} ${formatSigned(c.value, 1)}`).join("、")}
            table={
              <table data-testid="contrib-table">
                <thead>
                  <tr>
                    <th scope="col">條件</th>
                    <th scope="col">相對平均情況的貢獻（AQI）</th>
                  </tr>
                </thead>
                <tbody>
                  {contributions.map((c) => (
                    <tr key={c.key}>
                      <th scope="row">{labels[c.key] ?? c.key}</th>
                      <td className="num">{formatSigned(c.value, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            }
          >
            <DivergingBars rows={contributions.map((c) => ({ key: c.key, label: labels[c.key] ?? c.key, value: c.value }))} format={(v) => formatSigned(v, 1)} />
          </ChartFrame>
          <p className="how-to">
            <span className="how-to-title">怎麼讀</span>
            基準是訓練資料的平均狀態（AQI 約 {formatNumber(model.intercept)}）；基準加上各項貢獻才是預測值。往右的長條把預測推高，往左的拉低。
          </p>
        </Chapter>

        <Chapter
          no="02"
          title="敏感度掃描"
          takeaway={
            sweepInput && sweepLow !== undefined && sweepHigh !== undefined ? (
              <>
                其他條件固定，{sweepInput.label}從 {sweepInput.min} 調到 {sweepInput.max}，預測從 <strong>{formatNumber(sweepLow)}</strong> 變成{" "}
                <strong>{formatNumber(sweepHigh)}</strong>（{formatSigned(sweepHigh - sweepLow, 0)}）。
              </>
            ) : undefined
          }
        >
          <label className="field sweep-pick">
            <span className="label">敏感度掃描：只改變這一個條件</span>
            <select className="input" value={sweepInput?.key} onChange={(e) => setSweepKey(e.target.value)}>
              {model.inputs.map((i) => (
                <option key={i.key} value={i.key}>
                  {i.label}
                </option>
              ))}
            </select>
          </label>
          {sweepInput && (
            <ChartFrame
              title={`${sweepInput.label}從 ${sweepInput.min} 到 ${sweepInput.max} 時的預測`}
              summary={`其他條件固定，${sweepInput.label}最低時預測 ${formatNumber(sweepLow)}、最高時預測 ${formatNumber(sweepHigh)}。`}
              table={
                <table>
                  <thead>
                    <tr>
                      <th scope="col">{sweepInput.label}</th>
                      <th scope="col">預測 AQI</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sweep.map((p, i) => (
                      <tr key={i}>
                        <th scope="row">{formatNumber(p.value, decimals(sweepInput.key))}</th>
                        <td className="num">{formatNumber(p.aqi, 1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              }
            >
              <MultiLine
                series={[{ key: "sweep", label: "預測 AQI", values: sweep.map((p) => p.aqi), tone: 1 }]}
                labels={sweep.map((p) => `${formatNumber(p.value, decimals(sweepInput.key))}${sweepInput.unit ? ` ${sweepInput.unit}` : ""}`)}
                marker={markerIndex}
                format={(v) => String(v)}
              />
            </ChartFrame>
          )}
          <p className="how-to">
            <span className="how-to-title">怎麼讀</span>
            直線標出目前滑桿的位置。這是線性模型，所以曲線是直的；它反映資料中的關聯，不代表改變這個條件就會改變空氣。
          </p>
        </Chapter>
      </div>
    </div>
  );
}

export default function WhatIfPage() {
  useDocumentTitle("情境模擬");
  const model = useDataset("whatif.json");
  const overview = useDataset("overview.json");
  return (
    <div className="page stack">
      <PageHead kicker="瀏覽器端模型" title="情境模擬：哪些條件推動下一小時的 AQI？">
        <p className="lede">拖動條件滑桿，查看下一小時 AQI 預測與各項輸入的影響。模型資料包含三小時模型時點間的逐時插值；結果反映資料關聯，不代表因果。</p>
      </PageHead>
      <Gate<[WhatIf, Overview]> states={[model, overview]}>{(m, o) => <Simulator model={m} overview={o} />}</Gate>
    </div>
  );
}
