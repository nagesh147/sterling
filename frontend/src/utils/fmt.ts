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

/** Human-readable trade state labels */
const STATE_LABELS: Record<string, string> = {
  IDLE:                        'Watching',
  EARLY_SETUP_ACTIVE:          'Signal forming',
  CONFIRMED_SETUP_ACTIVE:      'Setup confirmed',
  ENTRY_ARMED_PULLBACK:        'Waiting for pullback entry',
  ENTRY_ARMED_CONTINUATION:    'Waiting for breakout entry',
  ENTERED:                     'Trade active',
  PARTIALLY_REDUCED:           'Partially closed',
  EXIT_PENDING:                'Exit pending',
  EXITED:                      'Closed',
  CANCELLED:                   'Cancelled',
  FILTERED:                    'Filtered',
};

export function fmtState(state: string | null | undefined): string {
  if (!state) return '—';
  return STATE_LABELS[state] ?? state;
}

/** Human-readable structure-type labels */
const STRUCTURE_LABELS: Record<string, string> = {
  naked_call:        'Long Call',
  naked_put:         'Long Put',
  bull_call_spread:  'Bull Call Spread',
  bear_put_spread:   'Bear Put Spread',
  bull_put_spread:   'Bull Put Spread (credit)',
  bear_call_spread:  'Bear Call Spread (credit)',
  no_trade:          'No Trade',
};

export function fmtStructure(type: string | null | undefined): string {
  if (!type) return '—';
  return STRUCTURE_LABELS[type] ?? type.replace(/_/g, ' ');
}

/** Direction label */
export function fmtDirection(dir: string | null | undefined): string {
  if (!dir) return '—';
  if (dir === 'long') return 'Bullish';
  if (dir === 'short') return 'Bearish';
  return dir;
}

/** Signal arrow label */
export function fmtArrow(type: string | null | undefined): string {
  if (!type) return '—';
  if (type === 'green') return 'Bullish signal';
  if (type === 'red') return 'Bearish signal';
  return type;
}
