/**
 * One shape for a signal, whichever engine produced it.
 *
 * The three boards grew independently and disagreed about basics: SuperTrend
 * called the trailing stop `stop_loss` and the hard stop `entry_sl`, ORB called
 * them `stopPremium` and nothing, Adaptive Edge worked in spot terms and had no
 * premium at all. A trader reading three boards had to hold three vocabularies.
 *
 * So the boards render this, and each engine supplies an adapter. The contract
 * is deliberately small — the columns every engine can honestly fill — and
 * anything an engine knows that the others do not goes in `sections`, which the
 * detail view renders verbatim. That is the difference between consistent and
 * lowest-common-denominator: the frame is shared, the substance is not.
 *
 * Every level is nullable on purpose. A missing number must render as "—", not
 * as zero: on a stop column, a fabricated 0 is a trade-destroying lie.
 */
import type { Stat } from './StatCard';

export type EngineId = 'supertrend' | 'navigator' | 'adaptive_edge' | 'orb' | 'atm_premium_imbalance';

export const ENGINE_LABEL: Record<EngineId, string> = {
  supertrend: 'SuperTrend',
  navigator: 'Navigator',
  adaptive_edge: 'Adaptive Edge',
  orb: 'ORB + VWAP',
  atm_premium_imbalance: 'ATM Premium Imbalance',
};

/** Short form for a badge, where the full name will not fit. */
export const ENGINE_TAG: Record<EngineId, string> = {
  supertrend: 'ST',
  navigator: 'NAV',
  adaptive_edge: 'AE',
  orb: 'ORB',
  atm_premium_imbalance: 'API',
};

/**
 * What the row is doing, in the order a trade passes through it.
 *
 * `armed` is the one worth naming carefully: the setup is valid and the trade
 * is not on yet. It is the only status that is a call to action, which is why
 * the board sorts it first and gives it the accent.
 */
export type BoardStatus =
  | 'armed'      // valid setup, not yet entered — act now
  | 'running'    // position open and the thesis still holds
  | 'weakening'  // open, but the exit rule has started counting against it
  | 'ended'      // closed, kept for the record
  | 'watching'   // scanned, conditions not met
  | 'error';     // could not be evaluated — never silently dropped

export const STATUS_LABEL: Record<BoardStatus, string> = {
  armed: 'Armed',
  running: 'Running',
  weakening: 'Weakening',
  ended: 'Ended',
  watching: 'Watching',
  error: 'Error',
};

/** Statuses that represent a tradable or live position, as opposed to noise. */
export const ACTIONABLE: readonly BoardStatus[] = ['armed', 'running', 'weakening'];

export type Direction = 'long' | 'short';

/** The traded thing. An engine may signal on spot and trade an option. */
export interface BoardInstrument {
  /** What is actually bought or sold, in full. */
  symbol: string;
  exchange: string;
  kind: 'option' | 'future' | 'equity' | 'index';
  optionType?: 'CE' | 'PE';
  strike?: number | null;
  expiry?: string | null;
  lotSize?: number | null;
  /** Kite subscription key, `EXCHANGE:SYMBOL`. Null when not quotable. */
  quoteKey: string | null;
}

/**
 * The price ladder, all in the instrument's own units.
 *
 * `stop` and `trail` are separate because they are separate rules: `stop` is
 * the hard stop set at entry and `trail` is where the ratchet has reached. A
 * board that shows only one of them cannot say whether a trade is protected at
 * its original risk or has already locked in gains.
 */
export interface BoardLevels {
  ltp: number | null;
  entry: number | null;
  stop: number | null;
  trail: number | null;
  target: number | null;
  /** Realised exit, once there is one. */
  exit: number | null;
}

export interface BoardSizing {
  /** Exchange lots. */
  lots: number | null;
  /** Units — lots x lot size. This is what every value calculation uses. */
  quantity: number | null;
  /** Rupees that can actually be lost if the stop is honoured. */
  atRiskInr: number | null;
  /** Rupees committed. For a bought option this equals the premium outlay. */
  deployedInr: number | null;
}

/** An engine-specific block, rendered in the detail view. */
export interface BoardSection {
  title: string;
  layout?: 'rows' | 'tiles';
  summary?: string;
  stats: Stat[];
}

export interface BoardSignal {
  id: string;
  engine: EngineId;
  /** The underlying the thesis is about, e.g. NIFTY — not the contract. */
  underlying: string;
  instrument: BoardInstrument;
  direction: Direction;
  status: BoardStatus;
  /** When the signal fired. Epoch ms, so grouping and sorting need no parsing. */
  atMs: number | null;
  levels: BoardLevels;
  sizing: BoardSizing;
  /** 0-100 where the engine publishes one. Not comparable across engines. */
  score: number | null;
  /**
   * Why this row is where it is. Required for `watching` and `error` — a row
   * that declines to trade and will not say why is the thing this codebase
   * keeps having to fix.
   */
  reason: string | null;
  /** Age of the quote behind `ltp`, seconds. Drives the staleness mark. */
  quoteAgeS?: number | null;
  /** Everything this engine knows that the others do not. */
  sections: BoardSection[];
}

/**
 * Sort order for the status column.
 *
 * Alphabetical would be meaningless here. This is the order a trade passes
 * through, which puts what needs acting on at the top and the historical
 * record at the bottom — the same reason ACTIONABLE exists.
 */
export const STATUS_RANK: Record<BoardStatus, number> = {
  armed: 0, running: 1, weakening: 2, watching: 3, ended: 4, error: 5,
};

/** Midnight-to-midnight bucket key in IST, which is the trading day here. */
export function sessionDayKey(atMs: number | null): string {
  if (atMs == null) return 'unknown';
  const ist = new Date(atMs + (5 * 60 + 30) * 60_000);
  return ist.toISOString().slice(0, 10);
}

/**
 * "Today" / "Yesterday" / "Thu 14 Aug" — relative to the IST trading day.
 *
 * `nowMs` is a parameter rather than a `Date.now()` call so the label is
 * testable and so a re-render at midnight cannot disagree with the grouping.
 */
export function sessionDayLabel(key: string, nowMs: number): string {
  if (key === 'unknown') return 'Undated';
  const today = sessionDayKey(nowMs);
  if (key === today) return 'Today';
  const yesterday = sessionDayKey(nowMs - 86_400_000);
  if (key === yesterday) return 'Yesterday';
  const [y, m, d] = key.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC',
  });
}

/**
 * Groups signals into trading days, newest day first, newest row first.
 *
 * Undated rows sort last rather than being dropped — an engine that failed to
 * stamp a signal still has something to say.
 */
export function groupByDay(signals: readonly BoardSignal[]): Array<{ key: string; signals: BoardSignal[] }> {
  const buckets = new Map<string, BoardSignal[]>();
  for (const s of signals) {
    const key = sessionDayKey(s.atMs);
    const list = buckets.get(key);
    if (list) list.push(s);
    else buckets.set(key, [s]);
  }
  return [...buckets.entries()]
    .sort((a, b) => (a[0] === 'unknown' ? 1 : b[0] === 'unknown' ? -1 : b[0].localeCompare(a[0])))
    .map(([key, list]) => ({
      key,
      signals: list.sort((a, b) => (b.atMs ?? 0) - (a.atMs ?? 0)),
    }));
}
