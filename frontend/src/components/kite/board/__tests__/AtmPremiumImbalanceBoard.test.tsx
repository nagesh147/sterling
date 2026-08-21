/**
 * The arm control and the empty states.
 *
 * This panel is the only board that can be legitimately empty *and* fine, so
 * what it says when there is nothing to show matters as much as the row itself:
 * "not armed" and "armed, waiting for a quote" are different situations and an
 * operator must not have to guess which one they are looking at.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { AtmPremiumImbalanceBoard } from '../AtmPremiumImbalanceBoard';

const IST = (5 * 60 + 30) * 60_000;
const OPEN = Date.UTC(2026, 7, 21, 9, 15) - IST;

let cfg: any = { config: { enabled: true } };
let snap: any = { data: undefined, isLoading: false, error: null };
let armState: any = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
let snapshotArgs: unknown[] = [];

vi.mock('../../../../hooks/useAtmPremiumImbalance', () => ({
  useAtmPremiumImbalanceConfig: () => ({ data: cfg }),
  useAtmPremiumImbalanceSnapshot: (...args: unknown[]) => { snapshotArgs = args; return snap; },
  useArmAtmPremiumImbalance: () => armState,
}));

function leg(over: any = {}) {
  return {
    instrument_id: '1', tradingsymbol: 'SENSEX26AUG77700PE', option_type: 'PE',
    lot_size: 20, ltp: 356.7, bid: 356.2, ask: 357.2,
    last_trade_ts_ms: OPEN + 900, session_origin: true, age_ms: 100,
    official_open: 356.7, ...over,
  };
}

function session(over: any = {}) {
  return {
    armed: true, finished: false, session_date: '2026-08-21', session_open_ms: OPEN,
    phase: 'armed', halt_reason: null, underlying: 'SENSEX', expiry: '2026-08-27',
    strike: 77700, quantity: 80, execution_mode: 'paper', quote_mode: 'COMPATIBILITY',
    protection_mode: 'NONE', trades_taken: 0,
    legs: { CE: leg({ option_type: 'CE', tradingsymbol: 'SENSEX26AUG77700CE', ltp: 500 }), PE: leg() },
    difference: 143.3, cheaper_leg: 'PE',
    signal: { action: 'BUY_PE', reason: 'cheaper_leg=PE', option_type: 'PE' },
    trade: null, ...over,
  };
}

beforeEach(() => {
  cfg = { config: { enabled: true } };
  snap = { data: { strategy: {}, config: {}, resolved: null, blockers: [], session: null },
           isLoading: false, error: null };
  armState = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
});

const view = () => render(<AtmPremiumImbalanceBoard nowMs={OPEN + 60_000} />);

describe('AtmPremiumImbalanceBoard', () => {
  it('tells the operator it is not armed, and how to start watching', () => {
    view();
    expect(screen.getByText('Not armed.')).toBeTruthy();
    expect(screen.getByText(/Arm the session to resolve the ATM pair/)).toBeTruthy();
  });

  it('refuses to arm while the strategy is disabled, and says why', () => {
    cfg = { config: { enabled: false } };
    view();
    const btn = screen.getByRole('button', { name: 'Arm session' }) as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    expect(btn.title).toBe('Enable the strategy in settings first');
    fireEvent.click(btn);
    expect(armState.mutate).not.toHaveBeenCalled();
  });

  it('arms on click when enabled', () => {
    view();
    fireEvent.click(screen.getByRole('button', { name: 'Arm session' }));
    expect(armState.mutate).toHaveBeenCalledTimes(1);
  });

  it('does not poll before anything is armed', () => {
    view();
    expect(snapshotArgs[1]).toBe(0);
  });

  it('starts polling once a live session exists', () => {
    snap = { ...snap, data: { ...snap.data, session: session() } };
    view();
    expect(snapshotArgs[1]).toBe(3000);
  });

  it('summarises the armed pair in the header', () => {
    snap = { ...snap, data: { ...snap.data, session: session() } };
    view();
    expect(screen.getByText(/SENSEX 77700/)).toBeTruthy();
    expect(screen.getByText('armed')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Re-arm' })).toBeTruthy();
  });

  it('shows blockers while nothing is armed, so the arm button is not a dead end', () => {
    snap = { ...snap, data: { ...snap.data, blockers: ['quantity must be a positive multiple of 20'] } };
    view();
    expect(screen.getByText('quantity must be a positive multiple of 20')).toBeTruthy();
  });

  it('hides blockers once a session is live — they no longer apply', () => {
    snap = { ...snap, data: { ...snap.data, blockers: ['stale blocker'], session: session() } };
    view();
    expect(screen.queryByText('stale blocker')).toBeNull();
  });

  it('reports a refused arm without pretending it worked', () => {
    armState = { ...armState, data: { status: 'pair_unresolved', message: 'no ATM strike' } };
    view();
    expect(screen.getByText(/Not armed — pair unresolved: no ATM strike/)).toBeTruthy();
  });

  it('stays quiet when the arm succeeded', () => {
    armState = { ...armState, data: { status: 'armed', message: null } };
    view();
    expect(screen.queryByText(/Not armed —/)).toBeNull();
  });

  it('surfaces a failed request instead of an empty board', () => {
    snap = { data: undefined, isLoading: false, error: new Error('502 bad gateway') };
    view();
    expect(screen.getByText(/Unavailable: 502 bad gateway/)).toBeTruthy();
  });

  it('says it is waiting for quotes, not that there is nothing to see', () => {
    snap = { ...snap, data: { ...snap.data, session: session({ legs: null, cheaper_leg: null, signal: null }) } };
    view();
    // the row exists, so the empty label must not be what we see
    expect(screen.queryByText(/Armed — waiting for both legs/)).toBeNull();
    expect(screen.getByText(/CE\/PE pending/)).toBeTruthy();
  });

  it('renders the row for a live pair', () => {
    snap = { ...snap, data: { ...snap.data, session: session() } };
    view();
    expect(screen.getByText('SENSEX26AUG77700PE')).toBeTruthy();
  });
});
