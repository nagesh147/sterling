import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { SterlingKiteEnginePane } from '../SterlingKiteEnginePane';

// Navigator is a peer engine with its own scan endpoint, so the one manual
// "Re-scan" control has to refresh whichever engines are actually on.
const supertrendScan = vi.fn(() => Promise.resolve());
const navigatorScan = vi.fn(() => Promise.resolve());
const cancelSupertrend = vi.fn();
const cancelNavigator = vi.fn();

const cfg: Record<string, any> = {
  engine_enabled: true,
  trail_target: 'fast',
  exit_mode: 'one_red',
  strike_moneyness: ['ATM'],
  scan_source: 'derivatives',
  scan_expiries: ['weekly'],
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

let navigatorEnabled = true;
let scanning = false;

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useEngineConfig: () => ({ data: cfg }),
  useSetEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  usePatchEngineConfig: () => ({ mutate: vi.fn(), isPending: false }),
  useEngineSignals: () => ({
    data: {
      generated_ms: 0, scanning, scanning_label: '', rows: [],
      next_scan_ms: 0, auto_scan: false, market_open: true,
    },
  }),
  useRunScan: () => ({ mutate: supertrendScan, mutateAsync: supertrendScan, isPending: false }),
  useCancelScan: () => ({ mutate: cancelSupertrend, isPending: false }),
}));

vi.mock('../../../hooks/useNavigator', () => ({
  useNavigatorConfig: () => ({ data: { record: { config: { enabled: navigatorEnabled } } } }),
  useRunNavigatorScan: () => ({ mutate: navigatorScan, mutateAsync: navigatorScan, isPending: false }),
  useCancelNavigatorScan: () => ({ mutate: cancelNavigator, isPending: false }),
}));

vi.mock('../../../hooks/useKite', () => ({ useKiteQuote: () => ({ data: {} }) }));

function renderPane() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <SterlingKiteEnginePane onSelectSignal={vi.fn()} />
    </QueryClientProvider>,
  );
}

describe('SterlingKiteEnginePane — manual re-scan across both engines', () => {
  beforeEach(() => {
    localStorage.clear();
    supertrendScan.mockClear();
    navigatorScan.mockClear();
    cancelSupertrend.mockClear();
    cancelNavigator.mockClear();
    cfg.engine_enabled = true;
    navigatorEnabled = true;
    scanning = false;
  });

  it('refreshes both engines when both are on', async () => {
    renderPane();
    fireEvent.click(screen.getByRole('button', { name: 'Re-scan both engines' }));
    await waitFor(() => expect(navigatorScan).toHaveBeenCalledTimes(1));
    expect(supertrendScan).toHaveBeenCalledTimes(1);
  });

  it('runs only Navigator when SuperTrend is off', async () => {
    cfg.engine_enabled = false;
    renderPane();
    fireEvent.click(screen.getByRole('button', { name: 'Run Navigator scan' }));
    await waitFor(() => expect(navigatorScan).toHaveBeenCalledTimes(1));
    expect(supertrendScan).not.toHaveBeenCalled();
  });

  it('runs only SuperTrend when Navigator is off', async () => {
    navigatorEnabled = false;
    renderPane();
    fireEvent.click(screen.getByRole('button', { name: 'Re-scan now' }));
    await waitFor(() => expect(supertrendScan).toHaveBeenCalledTimes(1));
    expect(navigatorScan).not.toHaveBeenCalled();
  });

  it('cancels every engine that a re-scan would have started', () => {
    scanning = true;
    renderPane();
    fireEvent.click(screen.getByRole('button', { name: 'Stop scan' }));
    expect(cancelSupertrend).toHaveBeenCalledTimes(1);
    expect(cancelNavigator).toHaveBeenCalledTimes(1);
  });

  it('cancels only Navigator when only Navigator could be scanning', () => {
    cfg.engine_enabled = false;
    scanning = true;
    renderPane();
    fireEvent.click(screen.getByRole('button', { name: 'Stop scan' }));
    expect(cancelNavigator).toHaveBeenCalledTimes(1);
    expect(cancelSupertrend).not.toHaveBeenCalled();
  });
});
