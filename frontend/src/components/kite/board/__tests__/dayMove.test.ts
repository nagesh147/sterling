/**
 * Today's move, as the board reports it.
 *
 * These three columns (Chg., Chg. % and the direction mark) existed only on
 * SuperTrend's bespoke table. Moving that table onto the shared board would have
 * deleted them — including the direction tinting fixed two commits ago — so they
 * come across first.
 *
 * Two rules here were bugs in the table this replaces, and both are about
 * refusing to state a number that cannot be derived honestly.
 */
import { describe, it, expect } from 'vitest';
import { dayMoveFromQuote, supertrendToBoard } from '../supertrendAdapter';

describe('dayMoveFromQuote', () => {
  it('measures from the previous close by default', () => {
    const m = dayMoveFromQuote({ last_price: 110, ohlc: { close: 100, open: 90 } });
    expect(m).toEqual({ abs: 10, pct: 10 });
  });

  it('measures from today’s open when asked', () => {
    const m = dayMoveFromQuote({ last_price: 110, ohlc: { close: 100, open: 90 } }, 'open');
    expect(m!.abs).toBeCloseTo(20);
    expect(m!.pct).toBeCloseTo(22.22, 2);
  });

  it('reports rupees with NO percentage when the feed sends only net_change', () => {
    // An option premium has no previous close on the day it starts trading —
    // exactly when this branch runs. Deriving a percentage from the last price
    // instead printed a ₹12 move on a ₹90 premium as "12.00%".
    const m = dayMoveFromQuote({ last_price: 90, net_change: 12 });
    expect(m).toEqual({ abs: 12, pct: null });
  });

  it('treats a zero base as no base', () => {
    // Dividing by it yields Infinity, and "Infinity%" beside a live position is
    // worse than nothing.
    const m = dayMoveFromQuote({ last_price: 50, ohlc: { close: 0 } });
    expect(m).toBeNull();
  });

  it('is null with no quote at all, so the cell reads “—” not zero', () => {
    // A zero would read as "flat". The truth is "not known yet".
    expect(dayMoveFromQuote(undefined)).toBeNull();
    expect(dayMoveFromQuote({})).toBeNull();
  });

  it('signs a fall correctly', () => {
    const m = dayMoveFromQuote({ last_price: 80, ohlc: { close: 100 } });
    expect(m).toEqual({ abs: -20, pct: -20 });
  });
});

/**
 * The marks SuperTrend supplies.
 *
 * Tested through the adapter rather than the board, because the interesting part
 * is the mapping from an engine's own vocabulary — `exit_reason` strings, a
 * navigator verdict — into badges the board can draw without knowing what any of
 * it means.
 */
describe('supertrend marks', () => {
  const row = (over: Record<string, unknown> = {}) => ({
    underlying: 'NIFTY', token: 1, exchange: 'NFO', regime: 'BULL',
    alignment: { fast: 1, mid: 1, slow: 1 }, direction: 'long', option_type: 'CE',
    spot: 24000, stop_loss: 23900, exit_state: '0/3 red', score: 80,
    timestamp_ms: 1_785_404_700_000, source: 'spot', is_active: true, is_fresh: false,
    target: null, legs: [], ...over,
  }) as never;

  const labels = (r: never, opts = {}) =>
    (supertrendToBoard([r], opts)[0].marks ?? []).map((m) => m.label);

  it('names the rule that actually closed the trade', () => {
    // Two different events. The board otherwise says only "ended".
    expect(labels(row({ exit_reason: 'trail breach at 120' }))).toContain('TSL exit');
    expect(labels(row({ exit_reason: 'time decay 40m' }))).toContain('Theta exit');
    expect(labels(row({ exit_reason: '3/3 red' }))).toContain('counter exit');
  });

  it('says nothing about an exit that has not happened', () => {
    expect(labels(row())).toEqual([]);
  });

  it('marks a re-entry, but only when an earlier entry is still running', () => {
    const key = 'NIFTY|long|spot';
    const earlier = new Map([[key, 1_785_404_600_000]]);
    expect(labels(row(), { originalEntryMs: earlier })).toContain('re-entry');
    // An entry at or after this row's own time is this row, not a prior one.
    const same = new Map([[key, 1_785_404_700_000]]);
    expect(labels(row(), { originalEntryMs: same })).not.toContain('re-entry');
  });

  it('carries Navigator’s verdict, since the two systems can disagree', () => {
    const marks = supertrendToBoard([row({ navigator: { status: 'CONFIRMED', reason_codes: ['flow'] } })])[0].marks ?? [];
    const nav = marks.find((m) => m.label.startsWith('Nav'));
    expect(nav?.label).toBe('Nav CONFIRMED');
    expect(nav?.tone, 'agreement reads as agreement').toBe('green');
  });

  it('does not colour a weak Navigator verdict as agreement', () => {
    const marks = supertrendToBoard([row({ navigator: { status: 'WATCHING', reason_codes: [] } })])[0].marks ?? [];
    expect(marks.find((m) => m.label.startsWith('Nav'))?.tone).toBe('dim');
  });
});
