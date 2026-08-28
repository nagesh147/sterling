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
import { dayMoveFromQuote } from '../supertrendAdapter';

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
