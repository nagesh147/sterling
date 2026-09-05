import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { SterlingKiteEnginePane } from '../SterlingKiteEnginePane';

const NOW = Date.now();
const YESTERDAY = NOW - 24 * 3600 * 1000;

const cfg = {
  engine_enabled: true, trail_target: 'fast', exit_mode: 'one_red', exit_aligned_trail: false,
  strike_moneyness: ['ATM'], scan_source: 'spot',
  scan_expiries: ['weekly', 'monthly'], scan_expiries_indices: null, scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50', 'BANKNIFTY'], scan_stocks: [], scan_all_stocks: false, auto_execute: false,
  risk_sizing: true, risk_pct: 1.0, max_lots: 10, expiry_square_off_days: 1, time_stop_bars: 0,
  stop_mode: 'both', directional_mode: false, vehicle: 'otm_options',
  enabled_vehicles: ['otm_options'], itm_depth: 'ITM10', target_delta: null,
  futures_expiry: 'near', adx_min: null, atr_pct_min: null, block_entry_minutes_before_close: 0,
  max_spread_pct: null, min_oi: null, max_daily_loss_pct: null, wire_risk_infra: false,
};

const todayRow = {
  underlying: 'NIFTY 50', token: 256265, exchange: 'NSE', regime: 'BULL',
  alignment: { fast: 1, mid: 1, slow: 1 }, direction: 'long', option_type: 'CE',
  spot: 24010, stop_loss: 23900, entry_sl: 23890, exit_state: '1/1 red',
  score: 85, timestamp_ms: NOW, source: 'spot', is_active: false, is_fresh: false,
  legs: [
    {
      moneyness: 'ATM', option_type: 'CE', option_symbol: 'NIFTY26AUG24000CE', strike: 24000,
      expiry: '2026-08-28', lot_size: 75, token: 44001,
    },
  ],
};

const yesterdayRow = {
  underlying: 'BANKNIFTY', token: 260105, exchange: 'NSE', regime: 'BULL',
  alignment: { fast: 1, mid: 1, slow: 1 }, direction: 'long', option_type: 'CE',
  spot: 52000, stop_loss: 51800, entry_sl: 51750, exit_state: '1/1 red',
  score: 80, timestamp_ms: YESTERDAY, source: 'spot', is_active: false, is_fresh: false,
  legs: [
    {
      moneyness: 'ATM', option_type: 'CE', option_symbol: 'BANKNIFTY26AUG52000CE', strike: 52000,
      expiry: '2026-08-28', lot_size: 15, token: 44002,
    },
  ],
};

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: cfg }),
  useSetEngineConfig: () => ({ mutate: vi.fn() }),
  usePatchEngineConfig: () => ({ mutate: vi.fn() }),
  useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({
    data: {
      generated_ms: NOW, scanning: false, scanning_label: '', rows: [todayRow, yesterdayRow],
      next_scan_ms: 0, auto_scan: false, market_open: true,
    },
  }),
  useRunScan: () => ({ mutate: vi.fn(), isPending: false }),
  useCancelScan: () => ({ mutate: vi.fn(), isPending: false }),
  useStockRegistry: () => ({ data: [] }),
}));

function renderPane() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <SterlingKiteEnginePane onSelectSignal={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe('SterlingKiteEnginePane — TODAY ONLY toggle', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders the TODAY ONLY toggle switch', () => {
    renderPane();
    expect(screen.getByRole('switch', { name: /TODAY ONLY/i })).toBeInTheDocument();
  });

  it('toggles TODAY ONLY on click and persists state to localStorage', () => {
    renderPane();
    const btn = screen.getByRole('switch', { name: /TODAY ONLY/i });
    expect(btn).toHaveAttribute('aria-checked', 'false');

    fireEvent.click(btn);
    expect(localStorage.getItem('kite_st_today_only')).toBe('true');
    expect(btn).toHaveAttribute('aria-checked', 'true');

    fireEvent.click(btn);
    expect(localStorage.getItem('kite_st_today_only')).toBe('false');
    expect(btn).toHaveAttribute('aria-checked', 'false');
  });

  it('filters out historical signals from yesterday when TODAY ONLY is active', () => {
    localStorage.setItem('kite_st_today_only', 'true');
    localStorage.setItem('kite_st_show_ended', 'true');
    renderPane();

    expect(screen.getByText('NIFTY 50')).toBeInTheDocument();
    expect(screen.queryByText('BANKNIFTY')).not.toBeInTheDocument();
  });
});
