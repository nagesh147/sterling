/**
 * The view filters that sit above every board: search, status, and how many
 * legs of one underlying to show.
 *
 * These are local-only. Nothing here is sent to the server and nothing changes
 * what is scanned or how a trade exits — that separation is the point, and the
 * toolbar draws a divider to say so.
 *
 * Which filters are *offered* is derived from the rows rather than hardcoded
 * per engine. "Show ended" appears when there are ended rows to show; "best
 * only" appears when some underlying actually has more than one leg. An engine
 * that grows a capability gets the control for free, and one that loses it
 * stops advertising a filter that would do nothing.
 */
import { useMemo, useState } from 'react';
import type { BoardSignal } from './boardTypes';

export interface BoardView {
  query: string;
  setQuery: (q: string) => void;
  showEnded: boolean;
  setShowEnded: (v: boolean) => void;
  bestOnly: boolean;
  setBestOnly: (v: boolean) => void;
  /** Rows after every filter, in board order. */
  visible: BoardSignal[];
  /** Whether each control has anything to act on. */
  offers: { ended: boolean; best: boolean };
  /** Counts for the summary line. */
  counts: { total: number; shown: number; ended: number };
}

/** Matches an underlying, a contract symbol, or an exchange. */
function matches(signal: BoardSignal, needle: string): boolean {
  if (!needle) return true;
  const q = needle.toLowerCase();
  return (
    signal.underlying.toLowerCase().includes(q)
    || signal.instrument.symbol.toLowerCase().includes(q)
    || signal.instrument.exchange.toLowerCase().includes(q)
  );
}

/**
 * One leg per underlying: the one closest to the money.
 *
 * "Best" used to be a bare glyph in the old header with no statement of what
 * made a leg best. It is the nearest strike, because that is the leg whose
 * premium tracks the underlying thesis most directly — and now the control
 * says so in its tooltip.
 */
function bestLegPerUnderlying(signals: BoardSignal[]): BoardSignal[] {
  const best = new Map<string, BoardSignal>();
  for (const s of signals) {
    const key = `${s.engine}:${s.underlying}:${s.direction}`;
    const held = best.get(key);
    if (!held) { best.set(key, s); continue; }
    const gap = (x: BoardSignal) => {
      const strike = x.instrument.strike;
      const spot = x.levels.ltp;
      return strike == null || spot == null ? Number.POSITIVE_INFINITY : Math.abs(strike - spot);
    };
    if (gap(s) < gap(held)) best.set(key, s);
  }
  return signals.filter((s) => best.get(`${s.engine}:${s.underlying}:${s.direction}`) === s);
}

export function useBoardView(signals: readonly BoardSignal[]): BoardView {
  const [query, setQuery] = useState('');
  const [showEnded, setShowEnded] = useState(false);
  const [bestOnly, setBestOnly] = useState(false);

  return useMemo(() => {
    const all = [...signals];
    const ended = all.filter((s) => s.status === 'ended').length;
    const perUnderlying = new Map<string, number>();
    for (const s of all) {
      const key = `${s.underlying}:${s.direction}`;
      perUnderlying.set(key, (perUnderlying.get(key) ?? 0) + 1);
    }
    const offers = {
      ended: ended > 0,
      best: [...perUnderlying.values()].some((n) => n > 1),
    };

    let visible = all.filter((s) => matches(s, query.trim()));
    if (!showEnded) visible = visible.filter((s) => s.status !== 'ended');
    if (bestOnly) visible = bestLegPerUnderlying(visible);

    return {
      query, setQuery, showEnded, setShowEnded, bestOnly, setBestOnly,
      visible, offers,
      counts: { total: all.length, shown: visible.length, ended },
    };
  }, [signals, query, showEnded, bestOnly]);
}
