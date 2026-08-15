import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { AdaptiveEdgeSettingsPanel } from '../AdaptiveEdgeSettingsPanel';

const { settingsQuery, snapshotQuery } = vi.hoisted(() => {
  const settings = {
    enabled: true,
    symbol: 'NIFTY-I',
    symbols: ['NIFTY-I'],
    scan_source: 'spot',
    scan_indices: ['NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'SENSEX'],
    scan_stocks: [],
    scan_all_stocks: false,
    scan_stock_contracts: false,
    strike_moneyness: ['ITM2', 'ITM1', 'ATM', 'OTM1', 'OTM2'],
    scan_expiries: ['weekly', 'monthly'],
    scan_expiries_indices: ['weekly', 'monthly'],
    w_short: 5,
    w_long: 15,
    stop_points: 80,
    trail_points: 40,
    profit_lock_activation_points: 50,
    profit_lock_offset_points: 15,
    persistence_bars: 3,
    scalp_favorable_points: 5,
    extended_favorable_points: 15,
    intraday_favorable_points: 25,
    tick_size: 1,
    ib_minutes: 15,
  };
  return {
    settingsQuery: { data: { settings, live_trading: false }, isLoading: false, error: null },
    snapshotQuery: { data: { software_complete: true, readiness: [] } },
  };
});

vi.mock('../../../hooks/useAdaptiveEdge', () => ({
  useAdaptiveEdgeSettings: () => settingsQuery,
  useAdaptiveEdgeSnapshot: () => snapshotQuery,
  useSetAdaptiveEdgeSettings: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock('../../../hooks/useSterlingKiteEngine', () => ({
  useStockRegistry: () => ({ data: [] }),
}));

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <AdaptiveEdgeSettingsPanel />
    </QueryClientProvider>,
  );
}

describe('AdaptiveEdgeSettingsPanel', () => {
  it('has the same dedicated engine sections as SuperTrend', () => {
    renderPanel();
    expect(screen.getByText('Chart source')).toBeInTheDocument();
    expect(screen.getByText('Instruments')).toBeInTheDocument();
    expect(screen.getByText('Contracts')).toBeInTheDocument();
    expect(screen.getByText('Trail tightness')).toBeInTheDocument();
    expect(screen.getByText('Exit rule')).toBeInTheDocument();
    expect(screen.getByText('Spot')).toBeInTheDocument();
    expect(screen.getByText('Strike range')).toBeInTheDocument();
    expect(screen.getByText('Index expiries')).toBeInTheDocument();
    expect(screen.getByText('Trail points')).toBeInTheDocument();
    expect(screen.getByText('Stop points')).toBeInTheDocument();
    expect(screen.getByLabelText('Flatten at 14:45 IST')).toBeDisabled();
  });
});
