/** Pure builders for the Navigator chart overlay.
 *
 * The chart component is a 3000-line imperative lightweight-charts host, so
 * every decision that can be made without a chart instance is made here
 * instead: which points to draw, which bar a marker belongs on, and which
 * caveats the legend has to admit to. That keeps the rules testable, and it
 * keeps the "don't draw what Navigator didn't see" invariants in one place.
 *
 * Navigator always evaluates hourly bars. Its evidence is laid over whatever
 * timeframe the chart is showing rather than recomputed for it — recomputing
 * on 5-minute candles would be a DIFFERENT evaluation from the one the engine
 * made, and an overlay that shows a setup the engine never saw is worse than
 * no overlay at all.
 */
import type {
  NavigatorChartBar, NavigatorChartDecision, NavigatorChartResponse, NavigatorProjectedRange,
} from '../../types/navigator';

export type OverlayPoint = { time: number; value: number };
export type OverlayMarker = {
  time: number;
  position: 'aboveBar' | 'belowBar' | 'inBar';
  color: string;
  shape: 'arrowUp' | 'arrowDown' | 'circle' | 'square';
  text: string;
  size?: number;
};

export type OverlayPalette = {
  long: string;
  short: string;
  neutral: string;
  muted: string;
  accent: string;
};

export const NAVIGATOR_INDICATORS = [
  ['nav-structure', 'Navigator AVWAP structure'],
  ['nav-range', 'Navigator projected range'],
  ['nav-flow', 'Navigator flow + gamma'],
  ['nav-decisions', 'Navigator setups & decisions'],
] as const;

export type NavigatorIndicatorKey = (typeof NAVIGATOR_INDICATORS)[number][0];

const NAVIGATOR_KEYS = new Set<string>(NAVIGATOR_INDICATORS.map(([key]) => key));

/** Chart timeframes whose bar timestamps always contain the hourly stamps, so
 *  hourly evidence can be laid over them without inventing time slots. */
export const HOURLY_COMPATIBLE_TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1H'];

export function isNavigatorIndicator(key: string): boolean {
  return NAVIGATOR_KEYS.has(key);
}

export function hasNavigatorIndicator(active: Iterable<string>): boolean {
  for (const key of active) if (NAVIGATOR_KEYS.has(key)) return true;
  return false;
}

/** The underlying whose Navigator evidence belongs on this chart, or null.
 *
 * Option contracts return null on purpose: Navigator's evidence is computed on
 * the UNDERLYING, so drawing its AVWAP band over a premium chart would put
 * index levels on a rupee-denominated axis. */
export function navigatorUnderlyingForSymbol(symbol: string | null | undefined): string | null {
  if (!symbol) return null;
  const [head, ...rest] = symbol.split(':');
  const exchange = rest.length ? head.toUpperCase() : '';
  const instrument = (rest.length ? rest.join(':') : head).trim();
  if (!instrument) return null;
  if (exchange === 'NFO' || exchange === 'BFO' || exchange === 'MCX' || exchange === 'CDS') return null;
  return instrument.toUpperCase();
}

function inRange(time: number, first: number, last: number): boolean {
  return time >= first && time <= last;
}

/** Nearest chart bar at or before `time`, within `tolerance` seconds.
 *
 * Hourly evidence has to land on a bar the chart actually drew. Snapping
 * BACKWARD (never forward) keeps a marker on the bar whose close produced the
 * evidence instead of the next bar, which would read as lookahead. */
export function snapToBar(times: number[], time: number, tolerance: number): number | null {
  if (!times.length || !Number.isFinite(time)) return null;
  let best: number | null = null;
  for (let i = 0; i < times.length; i += 1) {
    if (times[i] > time) break;
    best = times[i];
  }
  if (best == null) return null;
  return time - best <= tolerance ? best : null;
}

type BandKey = 'upper' | 'mid' | 'lower' | 'session_vwap' | 'vol_score' | 'atr' | 'relative_volume';

/** One band as chart points. Nulls are dropped rather than zero-filled: a
 *  warming-up bar has no AVWAP, and drawing it at 0 would drag the price
 *  scale to zero and imply a level that does not exist. */
export function bandSeries(
  bars: NavigatorChartBar[], key: BandKey, times: number[] = [],
): OverlayPoint[] {
  const first = times.length ? times[0] : -Infinity;
  const last = times.length ? times[times.length - 1] : Infinity;
  const out: OverlayPoint[] = [];
  for (const bar of bars) {
    const value = bar[key];
    if (value == null || !Number.isFinite(value)) continue;
    if (!inRange(bar.t, first, last)) continue;
    out.push({ time: bar.t, value });
  }
  return out;
}

const SETUP_LABEL: Record<string, string> = {
  PULLBACK_LONG: 'Pullback ↑',
  PULLBACK_SHORT: 'Pullback ↓',
  CONTINUATION_LONG: 'Continuation ↑',
  CONTINUATION_SHORT: 'Continuation ↓',
};

/** Every bar where a setup family held.
 *
 * Cooldown-suppressed bars are drawn too, but muted and labelled — "Navigator
 * saw this and deliberately ignored it" is exactly the thing a user cannot
 * infer from the signal board, and hiding it would make the cooldown look
 * like a gap in the logic. */
export function setupMarkers(
  bars: NavigatorChartBar[], times: number[], palette: OverlayPalette, tolerance = 3600,
): OverlayMarker[] {
  const out: OverlayMarker[] = [];
  for (const bar of bars) {
    if (!bar.setup) continue;
    const time = snapToBar(times, bar.t, tolerance);
    if (time == null) continue;
    const long = bar.setup.endsWith('_LONG');
    const label = SETUP_LABEL[bar.setup] || bar.setup;
    out.push(bar.fired
      ? {
        time, position: long ? 'belowBar' : 'aboveBar',
        color: long ? palette.long : palette.short,
        shape: long ? 'arrowUp' : 'arrowDown', text: label,
      }
      : {
        time, position: long ? 'belowBar' : 'aboveBar',
        color: palette.muted, shape: 'circle', text: `${label} (cooldown)`, size: 0.6,
      });
  }
  return out;
}

/** Confirmed swing anchors, marked at the bar they became USABLE.
 *
 * The pivot itself is older than its confirmation by `pivot_right_bars`, and
 * the marker text carries that lag. Drawing the anchor at the pivot bar would
 * imply Navigator knew about it while the bar was still forming. */
export function anchorMarkers(
  response: Pick<NavigatorChartResponse, 'anchors'>, times: number[], palette: OverlayPalette, tolerance = 3600,
): OverlayMarker[] {
  const out: OverlayMarker[] = [];
  for (const anchor of response.anchors) {
    const time = snapToBar(times, anchor.confirmed_t, tolerance);
    if (time == null) continue;
    out.push({
      time, position: anchor.kind === 'high' ? 'aboveBar' : 'belowBar',
      color: palette.accent, shape: 'square', size: 0.6,
      text: `${anchor.kind === 'high' ? 'High' : 'Low'} anchor confirmed`,
    });
  }
  return out;
}

const DECISION_TONE: Record<string, 'accept' | 'reject'> = {
  HIGH_CONVICTION: 'accept',
  CONFIRMED: 'accept',
};

export function decisionMarkers(
  decisions: NavigatorChartDecision[], times: number[], palette: OverlayPalette, tolerance = 3600,
): OverlayMarker[] {
  const out: OverlayMarker[] = [];
  for (const decision of decisions) {
    const time = snapToBar(times, decision.t, tolerance);
    if (time == null) continue;
    const accepted = DECISION_TONE[decision.status] === 'accept';
    const long = decision.direction === 'long';
    const score = decision.effective_score == null ? '' : ` ${Math.round(decision.effective_score)}`;
    out.push({
      time,
      position: long ? 'belowBar' : 'aboveBar',
      color: accepted ? (long ? palette.long : palette.short) : palette.neutral,
      shape: accepted ? (long ? 'arrowUp' : 'arrowDown') : 'circle',
      text: `${decision.status}${score}${decision.execution_eligible ? ' ✓' : ''}`,
    });
  }
  return out;
}

/** Option-flow oscillator as histogram bars, coloured by side. */
export function flowHistogram(
  response: Pick<NavigatorChartResponse, 'flow'>, times: number[], palette: OverlayPalette,
): Array<OverlayPoint & { color: string }> {
  const first = times.length ? times[0] : -Infinity;
  const last = times.length ? times[times.length - 1] : Infinity;
  const out: Array<OverlayPoint & { color: string }> = [];
  for (const point of response.flow) {
    if (point.oscillator == null || !Number.isFinite(point.oscillator)) continue;
    if (!inRange(point.t, first, last)) continue;
    out.push({
      time: point.t, value: point.oscillator,
      color: point.oscillator >= 0 ? palette.long : palette.short,
    });
  }
  return out;
}

/** Gamma has a direction and a confidence but no level, so the only honest
 *  single series for it is the signed confidence. */
export function gammaSeries(
  response: Pick<NavigatorChartResponse, 'gamma'>, times: number[],
): OverlayPoint[] {
  const first = times.length ? times[0] : -Infinity;
  const last = times.length ? times[times.length - 1] : Infinity;
  return response.gamma
    .filter((point) => Number.isFinite(point.signed_confidence) && inRange(point.t, first, last))
    .map((point) => ({ time: point.t, value: point.signed_confidence }));
}

export type ProjectedLevel = { label: string; price: number; kind: 'daily' | 'weekly' };

/** Frozen projected range edges as horizontal levels — only the ones that
 *  actually exist. An unavailable range is reported in the caveats instead,
 *  because "we have no projection" and "the projection is flat" differ. */
export function projectedLevels(response: Pick<NavigatorChartResponse, 'projected'>): ProjectedLevel[] {
  const out: ProjectedLevel[] = [];
  const add = (range: NavigatorProjectedRange | undefined, kind: 'daily' | 'weekly') => {
    if (!range?.available) return;
    if (range.upper != null) out.push({ label: `${kind === 'daily' ? 'Day' : 'Week'} proj high`, price: range.upper, kind });
    if (range.lower != null) out.push({ label: `${kind === 'daily' ? 'Day' : 'Week'} proj low`, price: range.lower, kind });
  };
  add(response.projected?.daily, 'daily');
  add(response.projected?.weekly, 'weekly');
  return out;
}

/** Everything the legend has to admit before the user reads the overlay as truth. */
export function overlayCaveats(
  response: NavigatorChartResponse | null | undefined, chartTimeframe: string,
): string[] {
  if (!response) return [];
  const caveats: string[] = [];
  if (!HOURLY_COMPATIBLE_TIMEFRAMES.includes(chartTimeframe)) {
    caveats.push(`Navigator evaluates hourly bars — switch to 1H or finer to line its evidence up with this ${chartTimeframe} chart.`);
  } else if (chartTimeframe !== '1H') {
    caveats.push(`Hourly Navigator evidence drawn on a ${chartTimeframe} chart.`);
  }
  const projected = response.projected;
  if (projected && !projected.daily.available && projected.daily.unavailable_reason) {
    caveats.push(`Daily projected range unavailable — ${projected.daily.unavailable_reason}.`);
  }
  if (projected && !projected.weekly.available && projected.weekly.unavailable_reason) {
    caveats.push(`Weekly projected range unavailable — ${projected.weekly.unavailable_reason}.`);
  }
  return [...caveats, ...(response.notes || [])];
}
