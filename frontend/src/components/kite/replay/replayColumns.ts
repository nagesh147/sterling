import type { CsvColumn } from './replayCsv';
import type { ReplaySignal, ReplayTrade } from '../../../hooks/useReplayStore';
import { rewardRisk } from './replayFormat';

/**
 * Column definitions shared by the rendered tables and the CSV export.
 *
 * They live together so the two cannot diverge — the previous surface exported
 * 20 trade columns from the dock and 17 from the summary, four of which were
 * always empty because the backend never populated them.
 */

export const SIGNAL_CSV_COLUMNS: readonly CsvColumn<ReplaySignal>[] = [
  { header: 'Time', value: (r) => r.time_iso },
  { header: 'Strategy', value: (r) => (r.strategy || '').toUpperCase() },
  { header: 'Contract', value: (r) => r.contract ?? '' },
  { header: 'Underlying', value: (r) => r.instrument },
  { header: 'Spot', value: (r) => r.spot ?? '' },
  { header: 'Direction', value: (r) => r.direction },
  { header: 'Strength', value: (r) => r.strength },
  { header: 'Entry', value: (r) => r.entry },
  { header: 'Stop Loss', value: (r) => r.stop },
  { header: 'Target', value: (r) => r.target },
  {
    header: 'R:R',
    value: (r) => {
      const rr = rewardRisk(r.entry, r.stop, r.target);
      return rr == null ? '' : rr.toFixed(2);
    },
  },
];

/**
 * Trade columns. The friction three are appended only when the replay actually
 * modelled friction — exporting a permanently blank `Slippage` column is the
 * paper version of showing `₹0.00` in the UI.
 */
export function tradeCsvColumns(hasFriction: boolean): readonly CsvColumn<ReplayTrade>[] {
  const base: CsvColumn<ReplayTrade>[] = [
    { header: 'Trade ID', value: (r) => r.trade_id },
    { header: 'Entry Time', value: (r) => r.entry_time_iso },
    { header: 'Exit Time', value: (r) => r.exit_time_iso },
    { header: 'Held (mins)', value: (r) => r.duration_mins },
    { header: 'Strategy', value: (r) => (r.strategy || '').toUpperCase() },
    { header: 'Contract', value: (r) => r.symbol },
    { header: 'Underlying', value: (r) => r.underlying },
    { header: 'Option Type', value: (r) => r.opt_type },
    { header: 'Strike', value: (r) => r.strike },
    { header: 'Lots', value: (r) => r.lots },
    { header: 'Quantity', value: (r) => r.quantity },
    { header: 'Entry Fill', value: (r) => r.entry_price },
    { header: 'Exit Fill', value: (r) => r.exit_price ?? '' },
    { header: 'Stop Loss', value: (r) => r.stop_loss },
    { header: 'Target', value: (r) => r.target_price },
    { header: 'Status', value: (r) => r.status },
    { header: 'PnL (INR)', value: (r) => r.pnl_usd },
    { header: 'PnL (%)', value: (r) => r.pnl_pct },
  ];
  if (!hasFriction) return base;
  return [
    ...base,
    { header: 'Raw Entry', value: (r) => r.raw_entry ?? '' },
    { header: 'Raw Exit', value: (r) => r.raw_exit ?? '' },
    { header: 'Slippage (INR)', value: (r) => (r.slippage == null ? '' : r.slippage.toFixed(2)) },
  ];
}

/** True when at least one trade carries measured friction. */
export function tradesHaveFriction(trades: readonly ReplayTrade[]): boolean {
  return trades.some((t) => t.slippage != null);
}

/** Stable row identity, so React does not remount every row on an append. */
export function signalKey(s: ReplaySignal): string {
  return `${s.time_iso}|${s.strategy}|${s.instrument}`;
}
