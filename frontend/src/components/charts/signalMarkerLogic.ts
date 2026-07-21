import type { EngineSignalRow, OptionLeg, SignalChartData } from '../../types/kiteEngine';

export type TrendDirection = 'up' | 'down';
export type TrendPoint = { direction: TrendDirection };

export function nearestTimeIndex(times: number[], targetSec: number, tolerance: number): number {
  if (!times.length || !Number.isFinite(targetSec)) return -1;
  let best = -1;
  let bestDiff = Infinity;
  for (let i = 0; i < times.length; i += 1) {
    const diff = Math.abs(times[i] - targetSec);
    if (diff < bestDiff) { best = i; bestDiff = diff; }
  }
  return bestDiff <= tolerance ? best : -1;
}

export function freshTripleAlignmentIndex(
  fast: TrendPoint[], mid: TrendPoint[], slow: TrendPoint[], times: number[],
  targetSec: number, wanted: TrendDirection, tolerance: number,
): number {
  const n = Math.min(fast.length, mid.length, slow.length, times.length);
  const all = (i: number) => fast[i]?.direction === wanted
    && mid[i]?.direction === wanted && slow[i]?.direction === wanted;
  let best = -1;
  let bestDiff = Infinity;
  for (let i = 1; i < n; i += 1) {
    if (!all(i) || all(i - 1)) continue;
    const diff = Math.abs(times[i] - targetSec);
    if (diff < bestDiff) { best = i; bestDiff = diff; }
  }
  return bestDiff <= tolerance ? best : -1;
}

/** Build chart metadata from the selected option contract, never from its grouped parent.
 * CE and PE are both long-premium BUY signals, so premium markers always seek a
 * fresh three-green transition regardless of the underlying BULL/BEAR regime. */
export function signalChartDataForPremiumLeg(
  row: EngineSignalRow, leg: OptionLeg,
): SignalChartData {
  const entryTs = leg.entry_timestamp_ms ?? leg.signal_timestamp_ms ?? row.timestamp_ms;
  const premiumTs = leg.signal_timestamp_ms ?? leg.entry_timestamp_ms ?? row.timestamp_ms;
  return {
    timestamp_ms: entryTs,
    direction: 'long',
    regime: row.regime,
    source: row.source === 'confluence' ? 'confluence' : 'derivatives',
    premium_signal_ms: premiumTs,
    marker_basis: 'premium',
  };
}
