import { categoryOf, DEFAULT_CATEGORIES } from "../lib/air";
import { formatNumber } from "../lib/format";
import type { Category } from "../lib/types";

/** AQI value with its category name; the colour is never the only cue. */
export function AqiChip({ value, categories = DEFAULT_CATEGORIES }: { value: number | null; categories?: Category[] }) {
  const category = categoryOf(value, categories);
  return (
    <span className="aqi-chip" data-category={category?.key ?? "none"}>
      {formatNumber(value)}
      <small>{category?.label ?? "無資料"}</small>
    </span>
  );
}

export function ScaleLegend({ categories = DEFAULT_CATEGORIES }: { categories?: Category[] }) {
  return (
    <ul className="scale-legend" aria-label="AQI 分級">
      {categories.map((c, i) => {
        const range = `${i === 0 ? 0 : (categories[i - 1]?.upper ?? 0) + 1}–${c.upper}`;
        return (
          <li key={c.key} data-category={c.key}>
            <span className="swatch" aria-hidden="true" />
            {c.label} <span className="muted">{range}</span>
          </li>
        );
      })}
    </ul>
  );
}
