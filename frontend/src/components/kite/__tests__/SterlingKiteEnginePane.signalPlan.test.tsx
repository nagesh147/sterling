import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// What the board tells the user about a signal's PLAN: entry premium, the stop it was
// taken with, whether the trail has already been breached, whether there is a target at
// all, and whether a row is a fresh opportunity or the same trend re-arming.

const cfg = {
  engine_enabled: true, trail_target: 'fast', exit_mode: 'three_red', exit_aligned_trail: false,
  strike_moneyness: ['ATM'], scan_source: 'spot',
  scan_expiries: ['weekly', 'monthly'], scan_expiries_indices: null, scan_expiries_stocks: null,
  scan_indices: ['NIFTY BANK'], scan_stocks: [], scan_all_stocks: false, auto_execute: false,
  risk_sizing: true, risk_pct: 1.0, max_lots: 10, expiry_square_off_days: 1, time_stop_bars: 0,
  stop_mode: 'both', directional_mode: false, vehicle: 'otm_options',
  enabled_vehicles: ['otm_options'], itm_depth: 'ITM10', target_delta: null,
  futures_expiry: 'near', adx_min: null, atr_pct_min: null, block_entry_minutes_before_close: 0,
  max_spread_pct: null, min_oi: null, max_daily_loss_pct: null, wire_risk_infra: false, hybrid_st_weight: 0.5,
};

type LegOverrides = {
  premium_spot?: number | null;
  premium_sl?: number | null;
  entry_sl?: number | null;
  premium_target?: number | null;
};

function makeRow(opts: {
  underlying?: string; token?: number; timestamp_ms?: number; is_active?: boolean;
  is_fresh?: boolean; source?: string; target?: number | null; leg?: LegOverrides; symbol?: string;
} = {}) {
  const {
    underlying = 'NIFTY BANK', token = 1, timestamp_ms = 1_785_404_700_000, is_active = true,
    is_fresh = false, source = 'spot', target = null, leg = {}, symbol = 'BANKNIFTY26AUG57000CE',
  } = opts;
  return {
    underlying, token, exchange: 'NFO', regime: 'BULL',
    alignment: { fast: 1, mid: 1, slow: 1 }, direction: 'long', option_type: 'CE',
    spot: 57147.5, stop_loss: 56891.3, entry_sl: 56500, exit_state: '0/3 red',
    score: 85, timestamp_ms, source, is_active, is_fresh, target,
    legs: [{
      moneyness: 'ITM1', option_type: 'CE', option_symbol: symbol, strike: 57000,
      expiry: '2026-08-25', lot_size: 35, token: token + 1000, is_active,
      premium_spot: leg.premium_spot ?? null,
      premium_sl: leg.premium_sl ?? null,
      entry_sl: leg.entry_sl ?? null,
      premium_target: leg.premium_target ?? null,
    }],
  };
}

function mockPane(rows: any[], quotes: Record<string, any> = {}) {
  vi.doMock('../../../hooks/useSterlingKiteEngine', () => ({
    useEngineConfig: () => ({ data: cfg }),
    useSetEngineConfig: () => ({ mutate: vi.fn() }),
    useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
    useEngineSignals: () => ({
      data: { generated_ms: 1, scanning: false, scanning_label: '', rows, next_scan_ms: 0, auto_scan: false, market_open: true },
    }),
    useRunScan: () => ({ mutate: vi.fn(), mutateAsync: vi.fn(() => Promise.resolve()), isPending: false }),
    useCancelScan: () => ({ mutate: vi.fn(), isPending: false }),
    useStockRegistry: () => ({ data: [] }),
  }));
  vi.doMock('../../../hooks/useKite', async () => {
    const actual: any = await vi.importActual('../../../hooks/useKite');
    return { ...actual, useKiteQuote: () => ({ data: quotes }) };
  });
}

async function renderPane() {
  const { SterlingKiteEnginePane: Pane } = await import('../SterlingKiteEnginePane');
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <Pane onSelectSignal={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe('signal plan on the board', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it('never quotes a delta for a leg with no solvable IV', async () => {
    // With no quote and no premium, blackScholesGreeks returns the INTRINSIC delta —
    // exactly 1.00 for an ITM call, with gamma/theta/vega all zero. Rendering that as
    // "(Δ1.00)" presents a missing-data answer as the most responsive contract on the
    // board, which is how a leg with no entry price ended up wearing the ▲ badge.
    mockPane([makeRow()]);
    await renderPane();
    expect(screen.getByText(/ITM1/)).toBeInTheDocument();
    expect(screen.queryByText(/Δ1\.00/)).not.toBeInTheDocument();
    // No numeric delta at all — the "Entry (Δpts)" column header is the only Δ allowed.
    expect(screen.queryByText(/Δ\d/)).not.toBeInTheDocument();
  });

  it('flags a leg whose live premium has already traded through its trailing stop', async () => {
    // The SuperTrend exit is a RED-COUNTER rule, so a leg sits at "0/3 red" and reads as
    // healthy while the premium is far below its trail. That gap is where a -14% open
    // position hides, so the board has to say it out loud.
    mockPane(
      [makeRow({ leg: { premium_spot: 1131.15, premium_sl: 1000.6, entry_sl: 694.2 } })],
      { 'NFO:BANKNIFTY26AUG57000CE': { last_price: 965 } },
    );
    await renderPane();
    expect(screen.getByText('TSL HIT')).toBeInTheDocument();
  });

  it('does not flag a leg trading above its trailing stop', async () => {
    mockPane(
      [makeRow({ leg: { premium_spot: 964.95, premium_sl: 845.85, entry_sl: 801.97 } })],
      { 'NFO:BANKNIFTY26AUG57000CE': { last_price: 965 } },
    );
    await renderPane();
    expect(screen.queryByText('TSL HIT')).not.toBeInTheDocument();
  });

  it('shows a real target for a Navigator-originated leg and "—" for a SuperTrend leg', async () => {
    mockPane([
      makeRow({ source: 'navigator', target: 57900, symbol: 'BANKNIFTY26AUG57000CE',
                leg: { premium_spot: 964.95, premium_sl: 845.85, entry_sl: 801.97, premium_target: 1420.5 } }),
    ]);
    await renderPane();
    expect(screen.getByText('1420.5')).toBeInTheDocument();
  });

  it('marks a later still-running entry on the same instrument as a re-entry, not a new setup', async () => {
    // The engine keeps every still-running entry transition, so one continuing trend can
    // occupy three rows at three very different entry prices. Only the first is a trade.
    mockPane([
      makeRow({ timestamp_ms: 1_785_123_900_000, token: 1 }),   // Mon — the original
      makeRow({ timestamp_ms: 1_785_404_700_000, token: 1 }),   // Thu — same trend re-arming
    ]);
    await renderPane();
    expect(screen.getAllByText('re-entry')).toHaveLength(1);
  });

  it('does not mark an entry as a re-entry when the earlier one has ended', async () => {
    mockPane([
      makeRow({ timestamp_ms: 1_785_123_900_000, token: 1, is_active: false }),
      makeRow({ timestamp_ms: 1_785_404_700_000, token: 1 }),
    ]);
    await renderPane();
    expect(screen.queryByText('re-entry')).not.toBeInTheDocument();
  });
});

describe('why a trade ended', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it('says the trailing stop closed it, even though the red counter never fired', async () => {
    // The whole point of enforcing the trail: exit_state still reads "0/3 red", so
    // without this the row looks like it ended for no stated reason.
    mockPane([{
      ...makeRow({ is_active: false }),
      exit_state: '0/3 red',
      exit_reason: 'trail breach (≤ 1000.63)',
    }]);
    await renderPane();
    expect(screen.getByText('TSL exit')).toBeInTheDocument();
  });

  it('distinguishes a red-counter close from a trail close', async () => {
    mockPane([{
      ...makeRow({ is_active: false }),
      exit_state: '3/3 red',
      exit_reason: 'red count exit 3/3 (three_red_signal)',
    }]);
    await renderPane();
    expect(screen.getByText('counter exit')).toBeInTheDocument();
    expect(screen.queryByText('TSL exit')).not.toBeInTheDocument();
  });

  it('shows no exit badge while the trade is still running', async () => {
    mockPane([makeRow()]);
    await renderPane();
    expect(screen.queryByText('TSL exit')).not.toBeInTheDocument();
    expect(screen.queryByText('counter exit')).not.toBeInTheDocument();
  });
  it('shows a brand-new Navigator signal as live, not as history', async () => {
    // A Navigator origination arrives fresh on its first bar. The board decided
    // "ended" from is_active alone, so the signal appeared struck through as a
    // past setup the instant it was generated. Ending a row clears BOTH flags.
    mockPane([makeRow({ source: 'navigator', is_active: false, is_fresh: true })]);
    await renderPane();
    expect(screen.getByText(/ITM1/)).toBeInTheDocument();
    expect(screen.getByText('Active now')).toBeInTheDocument();
  });

  it('still treats a row with neither flag as history', async () => {
    mockPane([makeRow({ is_active: false, is_fresh: false })]);
    await renderPane();
    expect(screen.queryByText('Active now')).not.toBeInTheDocument();
  });

  it('never renders an absolute rupee change as a percentage', async () => {
    // Kite's `net_change` is rupees. Assigning it to the percent cell printed a
    // 412-point BANKNIFTY day as "412.35%" while the Chg. column sat blank.
    mockPane([makeRow()], {
      'NSE:NIFTY BANK': { last_price: 57_147.5, net_change: 412.35 },
    });
    await renderPane();
    // It belongs in Chg. (rupees) ...
    expect(screen.getByText('412.35')).toBeInTheDocument();
    // ... and must never appear as a percentage.
    expect(screen.queryByText('412.35%')).not.toBeInTheDocument();
  });
});
