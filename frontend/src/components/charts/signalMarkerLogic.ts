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
