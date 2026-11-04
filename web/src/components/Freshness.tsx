import { formatAge, formatHour, hoursSince } from "../lib/format";

/**
 * The production build refreshes once a day; past this age the "current"
 * values and the 24-hour forecast are visibly out of date.
 */
export const STALE_AFTER_HOURS = 30;

/** "資料時間 11/3 20:00（約 2 小時前）" so a reader never mistakes old data for now. */
export function DataTime({ latest, nowMs }: { latest: string; nowMs: number }) {
  const age = hoursSince(latest, nowMs);
  return (
    <>
      資料時間 {formatHour(latest)}
      {age !== null && `（${formatAge(age)}）`}
    </>
  );
}

/** Warn when the published model snapshot has missed its daily refresh. */
export function StaleNotice({ latest, nowMs }: { latest: string; nowMs: number }) {
  const age = hoursSince(latest, nowMs);
  if (age === null || age < STALE_AFTER_HOURS) return null;
  return (
    <p className="notice" data-testid="stale-notice">
      這份模型資料是{formatAge(age)}的快照，已超過預定的每日更新時間；「目前」數值與預報可能已經過時，請以環境部即時資訊為準。
    </p>
  );
}
