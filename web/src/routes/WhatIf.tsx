import { useState } from "react";
import { useDataset, useDocumentTitle } from "../app/hooks";
import { AqiChip } from "../components/Aqi";
import { ChartFrame, DivergingBars, MultiLine } from "../components/charts";
import { Gate } from "../components/States";
import { defaultInputs, predictWhatIf, whatIfContributions } from "../lib/air";
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

  return (
    <div className="split whatif-layout">
      <section className="card whatif-inputs" aria-labelledby="inputs-title">
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

      <div className="stack">
        <section className="card whatif-result" aria-live="polite" aria-labelledby="result-title">
          <h2 id="result-title">下一小時 AQI 預測</h2>
          <p className="aqi-big" data-testid="whatif-prediction">
            {formatNumber(prediction)}
          </p>
          <AqiChip value={prediction} categories={overview.categories} />
          <p>
            80% 預測區間 <strong data-testid="whatif-interval">{formatNumber(low)}–{formatNumber(high)}</strong>
          </p>
          <p className="muted small">
            區間寬度來自 {model.calibration_size.toLocaleString("zh-TW")} 筆保留校準資料的殘差分位數；模型在你的瀏覽器裡計算，與 Python 版本逐位一致（誤差 &lt; 10⁻⁶）。
          </p>
        </section>

        <section className="card">
          <ChartFrame
            title="每個條件把預測推高或拉低多少"
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
          <p className="muted small">基準是訓練資料的平均狀態（AQI 約 {formatNumber(model.intercept)}）；各貢獻加總即為預測值。</p>
        </section>

        <section className="card">
          <label className="field">
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
              summary={`其他條件固定，${sweepInput.label}最低時預測 ${formatNumber(sweep[0]?.aqi)}、最高時預測 ${formatNumber(sweep.at(-1)?.aqi)}。`}
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
        </section>
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
      <header>
        <span className="eyebrow">瀏覽器端模型</span>
        <h1>情境模擬：哪些條件推動下一小時的 AQI？</h1>
        <p className="lede">
          拖動條件滑桿，查看下一小時 AQI 預測與各項輸入的影響。模型資料包含三小時模型時點間的逐時插值；結果反映資料關聯，不代表因果。
        </p>
      </header>
      <Gate<[WhatIf, Overview]> states={[model, overview]}>{(m, o) => <Simulator model={m} overview={o} />}</Gate>
    </div>
  );
}
