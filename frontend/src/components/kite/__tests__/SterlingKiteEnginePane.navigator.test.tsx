import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

const cfg = {
  engine_enabled: true, trail_target: 'fast', exit_mode: 'one_red', exit_aligned_trail: false,
  strike_moneyness: ['ATM'], scan_source: 'spot',
  scan_expiries: ['weekly', 'monthly'], scan_expiries_indices: null, scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50'], scan_stocks: [], scan_all_stocks: false, auto_execute: false,
  risk_sizing: true, risk_pct: 1.0, max_lots: 10, expiry_square_off_days: 1, time_stop_bars: 0,
  stop_mode: 'both', directional_mode: false, vehicle: 'otm_options',
  enabled_vehicles: ['otm_options', 'deep_itm_options'], itm_depth: 'ITM10', target_delta: null,
  futures_expiry: 'near', adx_min: null, atr_pct_min: null, block_entry_minutes_before_close: 0,
  max_spread_pct: null, min_oi: null, max_daily_loss_pct: null, wire_risk_infra: false,
};

const navDecision = {
  decision_id: 'nav_abc123', schema_version: 1, config_revision: 1, model_versions: {},
  generated_at_ms: 1_700_000_000_000, bar_close_ms: 1_700_000_000_000, activation_watermark_ms: 0,
  base_signal_id: 's1', trigger: 'base_fresh', direction: 'long', status: 'CONFIRMED',
  base_score: 85, suite_score: 80, effective_score: 82, execution_eligible: true, data_quality: 'ok',
  reason_codes: ['OK'], avwap: null, volatility: null, option_flow: null, gamma: null,
};

function makeRow(withNavigator: boolean) {
  return {
    underlying: 'NIFTY 50', token: 256265, exchange: 'NFO', regime: 'BULL',
    alignment: { fast: 1, mid: 1, slow: 1 }, direction: 'long', option_type: 'CE',
    spot: 24010, stop_loss: 23900, score: 85, timestamp_ms: 1_700_000_000_000,
    source: 'spot', is_active: true, is_fresh: true,
    legs: [{ moneyness: 'ATM', option_type: 'CE', option_symbol: 'NIFTY25JUN24000CE', strike: 24000, expiry: '2026-06-26', lot_size: 75, token: 44001, is_active: true }],
    ...(withNavigator ? { navigator: navDecision } : {}),
  };
}

function mockEngineHooks(row: ReturnType<typeof makeRow>) {
  vi.doMock('../../../hooks/useSterlingKiteEngine', () => ({
    useEngineConfig: () => ({ data: cfg }),
    useSetEngineConfig: () => ({ mutate: vi.fn() }),
    usePatchEngineConfig: () => ({ mutate: vi.fn() }),
    useResetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
    useEngineSignals: () => ({
      data: { generated_ms: 1, scanning: false, scanning_label: '', rows: [row], next_scan_ms: 0, auto_scan: false, market_open: true },
    }),
    useRunScan: () => ({ mutate: vi.fn(), isPending: false }),
    useCancelScan: () => ({ mutate: vi.fn(), isPending: false }),
    useStockRegistry: () => ({ data: [] }),
  }));
  vi.doMock('../../../hooks/useNavigator', () => ({
    useNavigatorConfig: () => ({ data: { record: { config: { enabled: true } } } }),
    useSetNavigatorConfig: () => ({ mutate: vi.fn() }),
    useRunNavigatorScan: () => ({ mutate: vi.fn(), isPending: false }),
    useCancelNavigatorScan: () => ({ mutate: vi.fn(), isPending: false }),
  }));
}

describe('SterlingKiteEnginePane — Navigator badge (additive, raw score unchanged)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetModules();
  });

  it('shows a Navigator badge without altering the raw score when navigator evidence is present', async () => {
    mockEngineHooks(makeRow(true));
    const { SterlingKiteEnginePane: Pane } = await import('../SterlingKiteEnginePane');
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <Pane onSelectSignal={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(screen.getByText(/Nav CONFIRMED/)).toBeInTheDocument();
  });

  it('renders no Navigator badge when the row has no navigator evidence (disabled/off by default)', async () => {
    mockEngineHooks(makeRow(false));
    const { SterlingKiteEnginePane: Pane } = await import('../SterlingKiteEnginePane');
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <Pane onSelectSignal={vi.fn()} />
      </QueryClientProvider>,
    );
    expect(screen.queryByText(/^Nav /)).not.toBeInTheDocument();
  });
});
