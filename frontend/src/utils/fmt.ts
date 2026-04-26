/** Safe number format — returns '—' for null/undefined/NaN/Infinity */
export function fmtN(val: number | null | undefined, decimals = 2): string {
  if (val == null || !isFinite(val)) return '—';
  return val.toFixed(decimals);
}

/** Safe currency format */
export function fmtUSD(val: number | null | undefined, decimals = 0): string {
  if (val == null || !isFinite(val)) return '—';
  return val.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Null-safe IVR color */
export function ivrColor(ivr: number | null | undefined): string {
  if (ivr == null) return '#555';
  if (ivr < 40) return '#44cc88';
  if (ivr < 60) return '#f0c040';
  if (ivr < 80) return '#f0a500';
  return '#cc4444';
}

/** Null-safe IVR bar width percent (0-100) */
export function ivrWidth(ivr: number | null | undefined): number {
  if (ivr == null) return 0;
  return Math.min(100, Math.max(0, ivr));
}

/** Relative age: "42s ago" / "7m ago" / "3h ago" / "2d ago" */
export function fmtAge(ts: number | null | undefined): string {
  if (ts == null) return '—';
  const diff = Date.now() - ts;
  if (diff < 0) return 'now';
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return `${Math.floor(diff / 86_400_000)}d ago`;
}

/** Smart timestamp: time-only today, "Apr 27 14:32" on other days */
export function fmtDateTime(ts: number | null | undefined): string {
  if (ts == null) return '—';
  const d = new Date(ts);
  const isToday = new Date().toDateString() === d.toDateString();
  if (isToday) return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
}
