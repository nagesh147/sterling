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
let simState: any = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
let stopSimState: any = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
let snapshotArgs: unknown[] = [];

vi.mock('../../../../hooks/useAtmPremiumImbalance', () => ({
  useAtmPremiumImbalanceConfig: () => ({ data: cfg }),
  useAtmPremiumImbalanceSnapshot: (...args: unknown[]) => { snapshotArgs = args; return snap; },
  useArmAtmPremiumImbalance: () => armState,
  useSimulateAtmPremiumImbalance: () => simState,
  useStopAtmPremiumImbalanceSimulation: () => stopSimState,
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
  snap = { data: { strategy: {}, config: {}, resolved: null, blockers: [], session: null,
                   sizing: undefined },
           isLoading: false, error: null };
  armState = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
  simState = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
  stopSimState = { mutate: vi.fn(), isPending: false, error: null, data: undefined };
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

describe('what arming would buy', () => {
  it('says the contract count, not just the lot count', () => {
    // "2 lots" is not a number of contracts, and the risk is in the contracts.
    snap = { ...snap, data: { ...snap.data,
      sizing: { mode: 'LOTS', lot_size: 20, quantity: 40 } } };
    view();
    expect(screen.getByText(/Will buy/)).toBeTruthy();
    expect(screen.getByText('40')).toBeTruthy();
    expect(screen.getByText(/\(2 × 20\)/)).toBeTruthy();
  });

  it('does not show the lot arithmetic in quantity mode', () => {
    snap = { ...snap, data: { ...snap.data,
      sizing: { mode: 'QUANTITY', lot_size: 20, quantity: 40 } } };
    view();
    expect(screen.getByText('40')).toBeTruthy();
    expect(screen.queryByText(/× 20/)).toBeNull();
  });

  it('stays quiet when no size is set', () => {
    snap = { ...snap, data: { ...snap.data,
      sizing: { mode: 'LOTS', lot_size: 20, quantity: 0 } } };
    view();
    expect(screen.queryByText(/Will buy/)).toBeNull();
  });
});

const REPLAY = {
  running: true, session_date: '2026-08-21', speed: 60, clock_ms: OPEN,
  clock_ist: '09:14:00', bars_total: 385, bars_done: 0, progress: 0,
  note: 'pre-open: refusing a carried-over quote', error: null,
  outcome: null, halt_reason: null, illustrative_only: true as const,
};

describe('replaying a past session', () => {
  it('offers a replay, and says nothing reaches a broker', () => {
    view();
    const btn = screen.getByRole('button', { name: 'Simulate' });
    expect(btn.title).toMatch(/Nothing is sent to a broker/);
    fireEvent.click(btn);
    expect(simState.mutate).toHaveBeenCalledWith(60);
  });

  it('marks the whole panel as a replay, unmissably', () => {
    // The numbers below this banner are not live. Anything subtler than a
    // labelled banner is a way to misread a simulation as a result.
    snap = { ...snap, data: { ...snap.data, simulation: REPLAY } };
    view();
    expect(screen.getByText('REPLAY')).toBeTruthy();
    expect(screen.getByText(/Real prices, simulated fills — not a backtest/)).toBeTruthy();
    expect(screen.getByText(/2026-08-21 · 09:14:00 IST · 60×/)).toBeTruthy();
  });

  it('shows what the strategy is doing right now', () => {
    snap = { ...snap, data: { ...snap.data, simulation: REPLAY } };
    view();
    expect(screen.getByText(/refusing a carried-over quote/)).toBeTruthy();
  });

  it('turns the button into a stop while it runs', () => {
    snap = { ...snap, data: { ...snap.data, simulation: REPLAY } };
    view();
    fireEvent.click(screen.getByRole('button', { name: 'Stop replay' }));
    expect(stopSimState.mutate).toHaveBeenCalled();
  });

  it('reports why a replay was refused', () => {
    simState = { ...simState, data: { status: 'live_session_active' } };
    view();
    expect(screen.getByText(/Replay not started — live session active/)).toBeTruthy();
  });

  it('surfaces a halt reason rather than just "halted"', () => {
    snap = { ...snap, data: { ...snap.data, simulation: {
      ...REPLAY, running: false, outcome: 'halted',
      halt_reason: 'premium_at_risk_exceeded: ₹35600.00 over the ₹25000.00 ceiling',
      note: 'finished: halted — premium_at_risk_exceeded: ₹35600.00 over the ₹25000.00 ceiling',
    } } };
    view();
    expect(screen.getByText(/premium_at_risk_exceeded/)).toBeTruthy();
  });

  it('says what premium the risk ceiling allows', () => {
    // The first real replay halted on exactly this and the board did not say so.
    snap = { ...snap, data: { ...snap.data,
      sizing: { mode: 'QUANTITY', lot_size: 20, quantity: 100,
                max_premium_at_risk_inr: 25000, max_affordable_premium: 250 } } };
    view();
    expect(screen.getByText(/premium up to ₹250.00/)).toBeTruthy();
  });
});

it('keeps the finished trade on screen instead of filtering it away', () => {
  // A replay that ends by hiding its own result is worse than no replay.
  snap = { ...snap, data: { ...snap.data, session: session({
    phase: 'done', finished: true,
    trade: {
      state: 'closed', option: 'PE', strike: 77500, quantity: 20,
      first_tick_price: 268.65, entry_order_price: 269.15, entry: 268.65,
      target: 268.65, high_water: 319.55, stop: 293.99, trigger: 291.3,
      exit_order_price: 290.8, exit: 290.8, points: 22.15, pnl: 443.0,
      slippage_vs_target: null, attempts: 1, quote_mode: 'COMPATIBILITY',
      halt_reason: null, protection: null, realised_pnl: 443.0,
    },
  }) } };
  view();
  expect(screen.getByText('SENSEX26AUG77700PE')).toBeTruthy();
});

