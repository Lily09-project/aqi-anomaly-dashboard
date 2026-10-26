export function formatNumber(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatSigned(value: number, digits = 1): string {
  const fixed = value.toFixed(digits);
  return value > 0 ? `+${fixed}` : fixed === `-${(0).toFixed(digits)}` ? (0).toFixed(digits) : fixed;
}

const TAIWAN_UTC_OFFSET_MS = 8 * 60 * 60 * 1_000;

/**
 * Parse Taiwan-local timestamps, honoring explicit ISO offsets when present.
 * Histories omit the offset; production forecasts may include +08:00.
 */
export function taiwanLocalTimestampMs(value: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?(Z|[+-]\d{2}:\d{2})?$/.exec(value);
  if (!match) return null;
  const [, yearText, monthText, dayText, hourText, minuteText, secondText, fraction, offsetText] = match;
  const year = Number(yearText);
  const month = Number(monthText);
  const day = Number(dayText);
  const hour = Number(hourText);
  const minute = Number(minuteText);
  const second = Number(secondText ?? 0);
  const millisecond = Number((fraction ?? "").slice(0, 3).padEnd(3, "0"));
  const localAsUtc = Date.UTC(year, month - 1, day, hour, minute, second, millisecond);
  const check = new Date(localAsUtc);
  if (
    !Number.isFinite(localAsUtc) ||
    check.getUTCFullYear() !== year ||
    check.getUTCMonth() !== month - 1 ||
    check.getUTCDate() !== day ||
    check.getUTCHours() !== hour ||
    check.getUTCMinutes() !== minute ||
    check.getUTCSeconds() !== second ||
    check.getUTCMilliseconds() !== millisecond
  ) {
    return null;
  }
  let offsetMs = TAIWAN_UTC_OFFSET_MS;
  if (offsetText === "Z") {
    offsetMs = 0;
  } else if (offsetText) {
    const offsetHours = Number(offsetText.slice(1, 3));
    const offsetMinutes = Number(offsetText.slice(4, 6));
    if (offsetHours > 23 || offsetMinutes > 59) return null;
    const sign = offsetText.startsWith("+") ? 1 : -1;
    offsetMs = sign * (offsetHours * 60 + offsetMinutes) * 60_000;
  }
  return localAsUtc - offsetMs;
}

/**
 * Exported timestamps use Taiwan clock values, optionally with an explicit +08:00 offset.
 * They are formatted as text so the viewer's own time zone never shifts them.
 */
export function formatHour(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
  if (!match) return iso;
  const [, , month, day, hour, minute] = match;
  return `${Number(month)}/${Number(day)} ${hour}:${minute}`;
}

export function formatDay(iso: string): string {
  return iso.slice(0, 10);
}

/** Clock time only ("23:00"). */
export function formatClock(iso: string): string {
  return iso.slice(11, 16) || iso;
}

/** Shift a local timestamp by whole hours, keeping the "YYYY-MM-DDTHH:MM" form. */
export function addHours(iso: string, hours: number): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
  if (!match) return iso;
  const [, y, mo, d, h, mi] = match.map(Number) as [number, number, number, number, number, number];
  const date = new Date(Date.UTC(y, mo - 1, d, h + hours, mi));
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}T${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}`;
}
