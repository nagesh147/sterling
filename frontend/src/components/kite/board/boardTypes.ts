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

export type EngineId = 'supertrend' | 'navigator' | 'adaptive_edge' | 'orb' | 'atm_premium_imbalance' | 'smart_money_options';

export const ENGINE_LABEL: Record<EngineId, string> = {
  supertrend: 'SuperTrend',
  navigator: 'Navigator',
  adaptive_edge: 'Adaptive Edge',
  orb: 'ORB + VWAP',
  atm_premium_imbalance: 'ATM Premium Imbalance',
  smart_money_options: 'Smart Money Multi-X',
};

/** Short form for a badge, where the full name will not fit. */
export const ENGINE_TAG: Record<EngineId, string> = {
  supertrend: 'ST',
  navigator: 'NAV',
  adaptive_edge: 'AE',
  orb: 'ORB',
  atm_premium_imbalance: 'API',
  smart_money_options: 'SMX',
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

/**
 * Where a signal came from, in its own engine's vocabulary.
 *
 * SuperTrend distinguishes the scan that found it (spot chart, the option's own
 * premium chart, both agreeing, or Navigator). Adaptive Edge distinguishes its
 * microstructure model from a plain spot scan. ORB distinguishes which feed the
 * numbers came from, because it is configurable and the two do not agree. ATM
 * distinguishes whether the quote behind the price traded in this session at
 * all, which is the rule its whole strategy turns on.
 *
 * Same slot on the row, four different meanings — which is the point. A shared
 * badge that said the same thing everywhere would be decoration.
 */
export interface BoardOrigin {
  label: string;
  hint: string;
  /** A `k` accent name, so the badge is themed rather than hardcoded. */
  tone: 'brand' | 'blue' | 'green' | 'purple' | 'amber' | 'dim';
}

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
  /** ATM / ITM1 / OTM2 — where the strike sits against the money. */
  moneyness?: string | null;
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
  /** This engine's own answer to "where did this come from". */
  origin?: BoardOrigin;
  /**
   * Short engine-specific marks on the row, after the origin badge.
   *
   * Where `origin` answers "where did this come from", these answer "what
   * else should I know before I act" — why a trade ended, how far an exit
   * counter has got, whether this is a re-entry on an instrument already
   * running. Each engine supplies its own; none is shared.
   */
  flags?: BoardOrigin[];
  /**
   * The underlying's own price, for the signal header.
   *
   * A parent row names an idea about an instrument, so it shows that
   * instrument's price — not a premium, which belongs to a contract.
   */
  underlyingPrice?: number | null;
  /**
   * Option delta, where the engine knows it.
   *
   * Shown beside the moneyness and used to mark the most responsive leg of a
   * signal, which is a comparison only worth making between siblings.
   */
  delta?: number | null;
  /** Everything this engine knows that the others do not. */
  sections: BoardSection[];
  /**
   * The contracts this signal is expressed through.
   *
   * A SuperTrend signal is one idea — "NIFTY, long, off the spot chart" —
   * carried by up to eighteen strikes. Flattening it into eighteen rows makes a
   * board you cannot read: NIFTY alone would occupy 37 consecutive lines that
   * differ only by strike.
   *
   * The parent holds what belongs to the idea (the underlying, where the signal
   * came from, when it fired); each child holds what belongs to one contract
   * (its premium, its stop, its size). The parent deliberately leaves the price
   * columns empty rather than borrowing a representative leg's numbers — a
   * thesis has no premium, and picking one leg to speak for the rest is a lie
   * about which one you would trade.
   *
   * Absent or empty means a leaf row, which is what most engines produce.
   */
  children?: BoardSignal[];
}

/** Every signal in a list, parents and their legs, in render order. */
export function flattenSignals(signals: readonly BoardSignal[]): BoardSignal[] {
  return signals.flatMap((s) => [s, ...(s.children ?? [])]);
}

/** True when any signal in the list carries legs. */
export const hasGroups = (signals: readonly BoardSignal[]) =>
  signals.some((s) => (s.children?.length ?? 0) > 0);

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

/** The bucket live positions float into, ahead of every dated one. */
export const LIVE_BUCKET = 'live';

/**
 * "Today" / "Yesterday" / "Thu 14 Aug" — relative to the IST trading day.
 *
 * `nowMs` is a parameter rather than a `Date.now()` call so the label is
 * testable and so a re-render at midnight cannot disagree with the grouping.
 */
export function sessionDayLabel(key: string, nowMs: number): string {
  if (key === LIVE_BUCKET) return 'Live now';
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
 *
 * With `liveFirst`, anything still open floats into one bucket ahead of every
 * dated one. Without it a position entered last Tuesday and still running sits
 * under "Tue 12 Aug", below three days of closed history, and the top of the
 * board reads as though nothing is on. The date buckets are then what they
 * should be: the log of entries whose trade has ended.
 */
export function groupByDay(
  signals: readonly BoardSignal[],
  { liveFirst = false }: { liveFirst?: boolean } = {},
): Array<{ key: string; signals: BoardSignal[] }> {
  const buckets = new Map<string, BoardSignal[]>();
  const push = (key: string, s: BoardSignal) => {
    const list = buckets.get(key);
    if (list) list.push(s);
    else buckets.set(key, [s]);
  };
  for (const s of signals) {
    push(liveFirst && ACTIONABLE.includes(s.status) ? LIVE_BUCKET : sessionDayKey(s.atMs), s);
  }
  const rank = (key: string) => (key === LIVE_BUCKET ? 0 : key === 'unknown' ? 2 : 1);
  return [...buckets.entries()]
    .sort((a, b) => rank(a[0]) - rank(b[0]) || b[0].localeCompare(a[0]))
    .map(([key, list]) => ({
      key,
      signals: list.sort((a, b) => (b.atMs ?? 0) - (a.atMs ?? 0)),
    }));
}

/**
 * Which legs of one signal are worth singling out.
 *
 * Two comparisons a trader makes across the strikes of a single idea, and
 * neither means anything between different signals — so they are computed per
 * group and never board-wide.
 *
 *   best reward:risk  the strike that pays most for what it puts at risk
 *   highest delta     the strike that moves most with the underlying
 *
 * A comparison needs something to compare, so a lone leg is marked with
 * neither: "best of one" is not information.
 */
export function markLegs(legs: readonly BoardSignal[]): Map<string, Set<'bestRR' | 'bestDelta'>> {
  const marks = new Map<string, Set<'bestRR' | 'bestDelta'>>();
  if (legs.length < 2) return marks;

  const add = (id: string, mark: 'bestRR' | 'bestDelta') => {
    const set = marks.get(id) ?? new Set<'bestRR' | 'bestDelta'>();
    set.add(mark);
    marks.set(id, set);
  };

  let bestRR: { id: string; value: number } | null = null;
  let bestDelta: { id: string; value: number } | null = null;
  for (const leg of legs) {
    const { entry, stop, target } = leg.levels;
    if (entry != null && stop != null && target != null) {
      const risk = Math.abs(entry - stop);
      if (risk > 0) {
        const rr = Math.abs(target - entry) / risk;
        if (!bestRR || rr > bestRR.value) bestRR = { id: leg.id, value: rr };
      }
    }
    if (leg.delta != null) {
      const d = Math.abs(leg.delta);
      if (!bestDelta || d > bestDelta.value) bestDelta = { id: leg.id, value: d };
    }
  }
  if (bestRR) add(bestRR.id, 'bestRR');
  if (bestDelta) add(bestDelta.id, 'bestDelta');
  return marks;
}

/**
 * A live premium that has fallen through its own trailing stop.
 *
 * Worth shouting about: on an engine whose exit is a counter rule rather than a
 * price rule, the leg still counts as running while this is true, and that is
 * exactly where an open drawdown builds.
 */
export function trailBreached(signal: BoardSignal): boolean {
  const { ltp, trail } = signal.levels;
  return signal.status !== 'ended' && ltp != null && trail != null && ltp <= trail;
}
