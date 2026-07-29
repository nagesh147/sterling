import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useKiteSettings } from '../../../store/useKiteSettings';
import { SterlingKiteEnginePane } from '../SterlingKiteEnginePane';

const signalRows: any[] = [];

const cfg = {
  engine_enabled: true,
  trail_target: 'fast',
  exit_mode: 'one_red',
  strike_moneyness: ['ATM'],
  scan_source: 'derivatives',
  scan_expiries: ['weekly', 'monthly'],
  scan_expiries_indices: null,
  scan_expiries_stocks: null,
  scan_indices: ['NIFTY 50'],
  scan_stocks: [],
  scan_all_stocks: false,
  auto_execute: false,
  risk_sizing: true,
  risk_pct: 1,
  max_lots: 10,
  stop_mode: 'both',
  directional_mode: false,
  vehicle: 'otm_options',
  enabled_vehicles: ['otm_options'],
  itm_depth: 'ITM10',
  target_delta: null,
  futures_expiry: 'near',
  adx_min: null,
  atr_pct_min: null,
  wire_risk_infra: false,
};

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: cfg }),
  useSetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({
    data: {
      generated_ms: 0,
      scanning: false,
      scanning_label: '',
      rows: signalRows,
      next_scan_ms: 0,
      auto_scan: false,
      market_open: true,
    },
  }),
  useRunScan: () => ({ mutate: vi.fn(), isPending: false }),
  useCancelScan: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../../../hooks/useKite', () => ({
  useKiteQuote: () => ({ data: {} }),
}));

function renderPane() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <SterlingKiteEnginePane onSelectSignal={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe('SterlingKiteEnginePane — table-only settings', () => {
  beforeEach(() => {
    localStorage.clear();
    signalRows.length = 0;
    cfg.scan_source = 'derivatives';
    useKiteSettings.getState().resetSignalTableSettings();
  });

  it('keeps table preferences exclusive and routes engine configuration to Connect', () => {
    const navListener = vi.fn();
    window.addEventListener('kite-nav-click', navListener);
    renderPane();

    expect(screen.queryByText('Signal table settings')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Scan report' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Signal table settings' }));

    expect(screen.getByText('Signal table settings')).toBeInTheDocument();
    expect(screen.getByText(/change only this table/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'List' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('checkbox', { name: 'Show ended setups' })).toBeChecked();

    // Engine controls must never leak back into the table preferences drawer.
    expect(screen.queryByText('Signal Discovery')).not.toBeInTheDocument();
    expect(screen.queryByText('Exit & Protection')).not.toBeInTheDocument();
    expect(screen.queryByText('Risk & Safeguards')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('checkbox', { name: 'Exchange' }));
    expect(useKiteSettings.getState().showExchange).toBe(false);

    fireEvent.click(screen.getByRole('checkbox', { name: 'Best signal per instrument' }));
    expect(localStorage.getItem('kite_st_best_only')).toBe('true');

    fireEvent.click(screen.getByRole('button', { name: /configure engine/i }));
    expect(localStorage.getItem('kite_connect_section')).toBe('engine');
    expect(navListener).toHaveBeenCalled();

    window.removeEventListener('kite-nav-click', navListener);
  });

  it('reveals retained rows instead of reporting that no signals exist', () => {
    localStorage.setItem('kite_st_show_ended', 'false');
    signalRows.push({
      underlying: 'NIFTY 50',
      token: 256265,
      exchange: 'NFO',
      regime: 'BULL',
      alignment: { fast: 1, mid: 1, slow: 1 },
      direction: 'long',
      option_type: 'CE',
      legs: [],
      spot: 25_000,
      stop_loss: 24_900,
      score: 85,
      timestamp_ms: Date.now(),
      source: 'spot',
      is_active: false,
      is_fresh: false,
    });

    renderPane();

    expect(screen.getByText(/1 recent setup is hidden by the current table filters/i)).toBeInTheDocument();
    expect(screen.queryByText(/No active or recent setups/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Show recent signals' }));

    expect(localStorage.getItem('kite_st_show_ended')).toBe('true');
    expect(screen.getByText('Today (ended)')).toBeInTheDocument();
  });

  it('keeps active spot candidate legs visible when ended legs are hidden', () => {
    localStorage.setItem('kite_st_show_ended', 'false');
    signalRows.push({
      underlying: 'NIFTY 50',
      token: 256265,
      exchange: 'NFO',
      regime: 'BULL',
      alignment: { fast: 1, mid: 1, slow: 1 },
      direction: 'long',
      option_type: 'CE',
      legs: [{
        moneyness: 'ATM',
        option_type: 'CE',
        option_symbol: 'NIFTY26JUN25000CE',
        strike: 25_000,
        expiry: '2026-06-26',
        lot_size: 75,
        token: 44001,
        is_active: false,
      }],
      spot: 25_000,
      stop_loss: 24_900,
      score: 85,
      timestamp_ms: Date.now(),
      source: 'spot',
      is_active: true,
      is_fresh: true,
    });

    renderPane();

    expect(screen.getByText('Active now')).toBeInTheDocument();
    expect(screen.getByText('25000')).toBeInTheDocument();
    expect(screen.queryByText(/no liquid contract/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/No option contract matched/i)).not.toBeInTheDocument();
  });

  it('shows the backend strike-resolution reason when a setup has no option legs', () => {
    signalRows.push({
      underlying: 'NIFTY 50',
      token: 256265,
      exchange: 'NFO',
      regime: 'BULL',
      alignment: { fast: 1, mid: 1, slow: 1 },
      direction: 'long',
      option_type: 'CE',
      legs: [],
      spot: 25_000,
      stop_loss: 24_900,
      score: 85,
      timestamp_ms: Date.now(),
      source: 'spot',
      is_active: true,
      is_fresh: true,
      resolution_reason: 'No listed contract matched the selected strike and expiry series.',
    });

    renderPane();

    expect(screen.getByText('No listed contract matched the selected strike and expiry series.')).toBeInTheDocument();
    expect(screen.queryByText(/no liquid contract/i)).not.toBeInTheDocument();
  });

  it('renders spot-source premium Entry, SL and TSL snapshots when present', () => {
    cfg.scan_source = 'spot';
    signalRows.push({
      underlying: 'NIFTY 50',
      token: 256265,
      exchange: 'NFO',
      regime: 'BULL',
      alignment: { fast: 1, mid: 1, slow: 1 },
      direction: 'long',
      option_type: 'CE',
      legs: [{
        moneyness: 'ATM',
        option_type: 'CE',
        option_symbol: 'NIFTY26JUN25000CE',
        strike: 25_000,
        expiry: '2026-06-26',
        lot_size: 75,
        token: 44001,
        is_active: true,
        premium_spot: 123.45,
        entry_sl: 101.2,
        premium_sl: 111.3,
      }],
      spot: 25_000,
      stop_loss: 24_900,
      score: 85,
      timestamp_ms: Date.now(),
      source: 'spot',
      is_active: true,
      is_fresh: true,
    });

    renderPane();

    expect(screen.getByText('Entry (Δpts)')).toBeInTheDocument();
    expect(screen.getByText('SL')).toBeInTheDocument();
    expect(screen.getByText('TSL')).toBeInTheDocument();
    expect(screen.getByText('123.45')).toBeInTheDocument();
    expect(screen.getByText('101.2')).toBeInTheDocument();
    expect(screen.getByText('111.3')).toBeInTheDocument();
  });
});
