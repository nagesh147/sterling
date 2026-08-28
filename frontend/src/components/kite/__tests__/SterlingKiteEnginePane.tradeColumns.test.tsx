/**
 * "Where is the show/hide option for the Buy/Sell buttons?"
 *
 * It was nowhere, on the renderer that is still the default. `trade` and `chart`
 * were defined in `SIGNAL_RIGHT_COLUMNS` when Buy/Sell/chart became columns on the
 * shared board — but the bespoke table's column menu is built from the PERSISTED
 * order, and that array never contained them. So the entries existed, the picker
 * never listed them, and the in-row buttons answered only to a Behaviour switch
 * two sections away. Defining a column is not offering it.
 *
 * Two halves, and both are needed: the menu has to list them, and the listing has
 * to actually govern the buttons.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { SterlingKiteEnginePane } from '../SterlingKiteEnginePane';
import { useKiteSettings } from '../../../store/useKiteSettings';

const cfg = {
  engine_enabled: true, trail_target: 'fast', exit_mode: 'one_red', exit_aligned_trail: false,
  strike_moneyness: ['ATM'], scan_source: 'derivatives',
  scan_expiries: ['weekly', 'monthly'], scan_expiries_indices: null, scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50'], scan_stocks: [], scan_all_stocks: false, auto_execute: false,
  risk_sizing: true, risk_pct: 1.0, max_lots: 10, expiry_square_off_days: 1, time_stop_bars: 0,
  stop_mode: 'both', directional_mode: false, vehicle: 'otm_options',
  enabled_vehicles: ['otm_options', 'deep_itm_options'], itm_depth: 'ITM10', target_delta: null,
  futures_expiry: 'near', adx_min: null, atr_pct_min: null, block_entry_minutes_before_close: 0,
  max_spread_pct: null, min_oi: null, max_daily_loss_pct: null, wire_risk_infra: false,
};

const row = {
  underlying: 'NIFTY 50', token: 256265, exchange: 'NFO', regime: 'BULL',
  alignment: { fast: 1, mid: 1, slow: 1 }, direction: 'long', option_type: 'CE',
  spot: 24010, stop_loss: 23900, entry_sl: 23890, exit_state: '0/1 red',
  score: 85, timestamp_ms: 1_700_000_000_000, source: 'derivatives',
  is_active: true, is_fresh: true, underlying_spot: 24010,
  legs: [{
    moneyness: 'ATM', option_type: 'CE', option_symbol: 'NIFTY25JUN24000CE', strike: 24000,
    expiry: '2026-06-26', lot_size: 75, token: 44001,
    premium_spot: 120.5, premium_sl: 100.0, entry_sl: 95.0, is_active: true,
  }],
};

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: cfg }),
  useSetEngineConfig: () => ({ mutate: vi.fn((_v: unknown, o?: { onSuccess?: () => void }) => o?.onSuccess?.()) }),
  usePatchEngineConfig: () => ({ mutate: vi.fn((_v: unknown, o?: { onSuccess?: () => void }) => o?.onSuccess?.()) }),
  useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({
    data: {
      generated_ms: 1, scanning: false, scanning_label: '', rows: [row],
      next_scan_ms: 0, auto_scan: false, market_open: true,
    },
  }),
  useRunScan: () => ({ mutate: vi.fn(), isPending: false }),
  useCancelScan: () => ({ mutate: vi.fn(), isPending: false }),
  useStockRegistry: () => ({ data: [] }),
}));

function wrap(node: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={qc}>{node}</QueryClientProvider>);
}

const buys = () => screen.queryAllByRole('button', { name: 'B' });
const sells = () => screen.queryAllByRole('button', { name: 'S' });
const charts = () => screen.queryAllByTitle('Chart');

beforeEach(() => {
  localStorage.clear();
  useKiteSettings.getState().resetSignalTableSettings();
});

describe('the column menu offers Trade and Chart', () => {
  it('lists them, which is the whole answer to "where is that option"', () => {
    // The COLUMNS menu sits in the board's own toolbar, not in the settings
    // drawer — so the pane is what has to be rendered to reach it.
    wrap(<SterlingKiteEnginePane onSelectSignal={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: /^Columns/ }));
    expect(screen.getByText('Trade')).toBeInTheDocument();
    expect(screen.getByText('Chart')).toBeInTheDocument();
  });
});

describe('and the listing governs the buttons', () => {
  it('shows Buy, Sell and the chart by default', () => {
    wrap(<SterlingKiteEnginePane onSelectSignal={vi.fn()} />);
    expect(buys().length).toBeGreaterThan(0);
    expect(sells().length).toBeGreaterThan(0);
    expect(charts().length).toBeGreaterThan(0);
  });

  it('hiding Trade removes Buy and Sell, and leaves the chart alone', () => {
    useKiteSettings.getState().toggleSignalCol('trade');
    wrap(<SterlingKiteEnginePane onSelectSignal={vi.fn()} />);
    expect(buys()).toHaveLength(0);
    expect(sells()).toHaveLength(0);
    // One column's toggle must not take the other's button with it.
    expect(charts().length).toBeGreaterThan(0);
  });

  it('hiding Chart removes the chart, and leaves Buy and Sell alone', () => {
    useKiteSettings.getState().toggleSignalCol('chart');
    wrap(<SterlingKiteEnginePane onSelectSignal={vi.fn()} />);
    expect(charts()).toHaveLength(0);
    expect(buys().length).toBeGreaterThan(0);
    expect(sells().length).toBeGreaterThan(0);
  });

  it('adds no empty width for them among the price cells', () => {
    // They are drawn by the action cluster, not as price cells. The cell wrapper
    // applies `col.width` whatever the cell returns, so letting them through the
    // price-cell map would put 126px of nothing in every row.
    wrap(<SterlingKiteEnginePane onSelectSignal={vi.fn()} />);
    const widths = Array.from(document.querySelectorAll('.st-prices > div'))
      .map((d) => (d as HTMLElement).style.width);
    expect(widths).not.toContain('92px');
    expect(widths).not.toContain('34px');
  });
});
