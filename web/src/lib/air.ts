/**
 * AQI categories, the outing planner and the in-browser what-if model.
 * Each function mirrors a Python module and is tested against it.
 */
import { taiwanLocalTimestampMs } from "./format";
import type { Category, QuantileHour, WhatIf } from "./types";

export const DEFAULT_CATEGORIES: Category[] = [
  { upper: 50, key: "good", label: "良好" },
  { upper: 100, key: "moderate", label: "普通" },
  { upper: 150, key: "sensitive", label: "對敏感族群不健康" },
  { upper: 200, key: "unhealthy", label: "對所有族群不健康" },
  { upper: 300, key: "very-unhealthy", label: "非常不健康" },
  { upper: 500, key: "hazardous", label: "危害" },
];

/** Activity guidance per band, paraphrased from the Ministry of Environment's AQI table. */
export const ADVICE: Record<string, { general: string; sensitive: string }> = {
  good: { general: "正常戶外活動。", sensitive: "正常戶外活動。" },
  moderate: { general: "正常戶外活動。", sensitive: "極特殊敏感族群建議留意可能產生的咳嗽或呼吸急促症狀，仍可正常戶外活動。" },
  sensitive: {
    general: "一般民眾如果有不適，應考慮減少戶外活動。",
    sensitive: "有心臟、呼吸道及心血管疾病者、孩童及老年人，建議減少體力消耗活動及戶外活動，必要外出應配戴口罩。",
  },
  unhealthy: {
    general: "一般民眾如果有不適，應減少體力消耗，特別是減少戶外活動。",
    sensitive: "有心臟、呼吸道及心血管疾病者、孩童及老年人，建議留在室內並減少體力消耗活動，必要外出應配戴口罩。",
  },
  "very-unhealthy": {
    general: "一般民眾應減少戶外活動。",
    sensitive: "有心臟、呼吸道及心血管疾病者、孩童及老年人應留在室內並減少體力消耗活動。",
  },
  hazardous: {
    general: "一般民眾應避免戶外活動，室內應緊閉門窗。",
    sensitive: "有心臟、呼吸道及心血管疾病者、孩童及老年人應留在室內並避免體力消耗活動。",
  },
};

export function categoryOf(aqi: number | null | undefined, categories: Category[] = DEFAULT_CATEGORIES): Category | null {
  if (aqi === null || aqi === undefined || Number.isNaN(aqi)) return null;
  return categories.find((c) => aqi <= c.upper) ?? categories[categories.length - 1] ?? null;
}

/** P(AQI > threshold) from the piecewise-linear CDF through P10/P50/P90 (src/analytics/planner.py). */
export function exceedanceProbability(hour: Pick<QuantileHour, "p10" | "p50" | "p90">, threshold: number): number {
  const xs = [hour.p10, hour.p50, hour.p90];
  const ps = [0.1, 0.5, 0.9];
  const [x0, x1, x2] = xs as [number, number, number];
  let cdf: number;
  if (threshold <= x0) {
    const slope = (ps[1]! - ps[0]!) / Math.max(x1 - x0, 1e-9);
    cdf = ps[0]! - slope * (x0 - threshold);
  } else if (threshold >= x2) {
    const slope = (ps[2]! - ps[1]!) / Math.max(x2 - x1, 1e-9);
    cdf = ps[2]! + slope * (threshold - x2);
  } else {
    const segment = threshold <= x1 ? 0 : 1;
    const lo = xs[segment]!;
    const hi = xs[segment + 1]!;
    cdf = ps[segment]! + ((ps[segment + 1]! - ps[segment]!) * (threshold - lo)) / Math.max(hi - lo, 1e-9);
  }
  return 1 - Math.min(Math.max(cdf, 0), 1);
}


/** Keep only forecast hours that have not started yet, using Taiwan-local timestamps. */
export function futureForecast<T extends Pick<QuantileHour, "t">>(forecast: readonly T[], nowMs = Date.now()): T[] {
  if (!Number.isFinite(nowMs)) return [];
  return forecast.filter((hour) => {
    const instant = taiwanLocalTimestampMs(hour.t);
    return instant !== null && instant >= nowMs;
  });
}

export interface Window {
  start: number;
  risk: number;
  meanP50: number;
}

/** Average exceedance probability of every window of the given length, by start index. */
export function windowRisks(forecast: Pick<QuantileHour, "p10" | "p50" | "p90">[], hours: number, threshold: number): number[] {
  if (hours < 1 || hours > forecast.length) return [];
  const risks = forecast.map((h) => exceedanceProbability(h, threshold));
  const out: number[] = [];
  for (let start = 0; start + hours <= forecast.length; start += 1) {
    let risk = 0;
    for (let i = start; i < start + hours; i += 1) risk += risks[i] ?? 0;
    out.push(risk / hours);
  }
  return out;
}

/** Lowest average exceedance probability; ties prefer cleaner air, then the earlier start. */
export function bestWindow(forecast: Pick<QuantileHour, "p10" | "p50" | "p90">[], hours: number, threshold: number): Window | null {
  const risks = windowRisks(forecast, hours, threshold);
  let best: Window | null = null;
  const eps = 1e-12;
  risks.forEach((risk, start) => {
    let meanP50 = 0;
    for (let i = start; i < start + hours; i += 1) meanP50 += forecast[i]?.p50 ?? 0;
    meanP50 /= hours;
    if (!best || risk < best.risk - eps || (Math.abs(risk - best.risk) <= eps && meanP50 < best.meanP50 - eps)) {
      best = { start, risk, meanP50 };
    }
  });
  return best;
}

function featureVector(model: WhatIf, inputs: Record<string, number>): number[] {
  const angle = (2 * Math.PI * (inputs.hour ?? 0)) / 24;
  const base = model.feature_order.slice(0, -2).map((key) => inputs[key] ?? 0);
  return [...base, Math.sin(angle), Math.cos(angle)];
}

/** Same arithmetic as src/analytics/whatif.predict_from_payload. */
export function predictWhatIf(model: WhatIf, inputs: Record<string, number>): number {
  return featureVector(model, inputs).reduce(
    (sum, value, i) => sum + ((value - (model.means[i] ?? 0)) / (model.scales[i] ?? 1)) * (model.coefficients[i] ?? 0),
    model.intercept,
  );
}

/** Contribution of each input relative to an average hour (hour sin/cos combined). */
export function whatIfContributions(model: WhatIf, inputs: Record<string, number>): { key: string; value: number }[] {
  const terms = featureVector(model, inputs).map((value, i) => ((value - (model.means[i] ?? 0)) / (model.scales[i] ?? 1)) * (model.coefficients[i] ?? 0));
  const n = model.feature_order.length;
  const keys = model.feature_order.slice(0, -2);
  return [...keys.map((key, i) => ({ key, value: terms[i] ?? 0 })), { key: "hour", value: (terms[n - 2] ?? 0) + (terms[n - 1] ?? 0) }];
}

export function defaultInputs(model: WhatIf): Record<string, number> {
  return Object.fromEntries(model.inputs.map((input) => [input.key, input.default]));
}
