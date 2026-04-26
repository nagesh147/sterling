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
