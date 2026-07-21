import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useKiteSettings } from '../../../store/useKiteSettings';
import { SterlingKiteEnginePane } from '../SterlingKiteEnginePane';

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
      rows: [],
      next_scan_ms: 0,
      auto_scan: false,
      market_open: true,
    },
  }),
  useRunScan: () => ({ mutate: vi.fn(), isPending: false }),
  useCancelScan: () => ({ mutate: vi.fn(), isPending: false }),
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
    expect(screen.queryByText('Signal discovery')).not.toBeInTheDocument();
    expect(screen.queryByText('Exit & protection')).not.toBeInTheDocument();
    expect(screen.queryByText('Risk & safeguards')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('checkbox', { name: 'Exchange' }));
    expect(useKiteSettings.getState().showExchange).toBe(false);

    fireEvent.click(screen.getByRole('checkbox', { name: 'Best signal per instrument' }));
    expect(localStorage.getItem('kite_st_best_only')).toBe('true');

    fireEvent.click(screen.getByRole('button', { name: /configure engine/i }));
    expect(localStorage.getItem('kite_connect_section')).toBe('engine');
    expect(navListener).toHaveBeenCalled();

    window.removeEventListener('kite-nav-click', navListener);
  });
});
