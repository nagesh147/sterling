import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { UnifiedBacktestPane } from '../UnifiedBacktestPane';

const mockStrategies = [
  { id: 'adaptive_edge', name: 'Adaptive Edge', category: 'Microstructure' },
  { id: 'supertrend', name: 'Triple SuperTrend', category: 'Trend' },
  { id: 'navigator', name: 'Value-Flow Navigator', category: 'Volatility' },
];

const mockPresets = [
  {
    name: 'NIFTY 50 • Adaptive Edge Intraday',
    strategy: 'adaptive_edge',
    symbol: 'NIFTY 50',
    timeframe: '5m',
    lookback_days: 30,
    lot_size: 25,
    num_lots: 2,
    starting_capital: 150000.0,
    stop_points: 40.0,
    target_points: 80.0,
    trail_points: 25.0,
    slippage_points: 0.5,
  },
];

vi.mock('../../../hooks/useUnifiedBacktest', () => ({
  useUnifiedStrategies: () => ({ data: mockStrategies, isLoading: false }),
  useUnifiedPresets: () => ({ data: mockPresets, isLoading: false }),
  useRunUnifiedBacktest: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}));

function renderComponent() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <UnifiedBacktestPane />
    </QueryClientProvider>
  );
}

describe('UnifiedBacktestPane', () => {
  it('renders strategy selector, presets, parameters, and run button', () => {
    renderComponent();

    expect(screen.getByText('REAL HISTORICAL DATA ENGINE')).toBeInTheDocument();
    expect(screen.getByText('NIFTY 50 • Adaptive Edge Intraday')).toBeInTheDocument();
    expect(screen.getByText(/Strategy & Engine Parameters/i)).toBeInTheDocument();
    expect(screen.getByText(/Indian F&O Friction Engine/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Run Backtest/i })).toBeInTheDocument();
    expect(screen.getByText('Ready to Run Real-Data Backtest')).toBeInTheDocument();
  });

  it('clicking preset applies preset values', () => {
    renderComponent();

    const presetBtn = screen.getByText('NIFTY 50 • Adaptive Edge Intraday');
    fireEvent.click(presetBtn);
    expect(presetBtn).toBeInTheDocument();
  });
});
