import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const runtime = vi.hoisted(() => ({
  installChartParityRuntime: vi.fn(),
  setChartParityContext: vi.fn(),
  removeChartParityContext: vi.fn(),
  setChartVisibleRange: vi.fn(),
}));

vi.mock('../TradingViewKiteChartLegacy', () => ({
  TradingViewKiteChart: () => <div data-testid="legacy-chart" />,
}));

vi.mock('../chartParityRuntime', () => ({
  CHART_CROSSHAIR_EVENT: 'sterling:kite-chart-crosshair',
  CHART_RANGE_KEYS: ['1D', '5D', 'ALL'],
  normalizeChartCandles: (candles: any[]) => candles,
  ...runtime,
}));

import { TradingViewKiteChart } from '../TradingViewKiteChart';

const theme = {
  bg: '#fff', surface: '#f7f7f7', border: '#ddd', text: '#111', dim: '#777',
  blue: '#2962ff', red: '#e05260', green: '#2db784', fontFamily: 'sans-serif',
};

const candles = [
  { time: 10, open: 100, high: 104, low: 99, close: 102, volume: 1_000 },
  { time: 20, open: 102, high: 108, low: 101, close: 106, volume: 1_100 },
];

function withQueryClient(node: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{node}</QueryClientProvider>;
}

function renderChart(overrides: Record<string, unknown> = {}) {
  return render(withQueryClient(
    <TradingViewKiteChart
      symbol="NSE:RELIANCE"
      rawCandles={candles}
      tf="15m"
      theme={theme}
      activeIndicators={new Set(['st-mid'])}
      params={{ stMidPeriod: 14, stMidMult: 2 }}
      {...overrides}
    />,
  ));
}

describe('TradingViewKiteChart parity shell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows the instrument, OHLC change and active SuperTrend legend', () => {
    renderChart();
    expect(screen.getAllByText('RELIANCE').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('button', { name: 'Timeframe' })).toHaveTextContent('15m');
    expect(screen.getByText('SuperTrend 14 2')).toBeTruthy();
    expect(screen.getByText(/\+4\.00 \(\+3\.92%\)/)).toBeTruthy();
    expect(screen.getByTestId('legacy-chart')).toBeTruthy();
  });

  it('applies a scoped chart range from the bottom toolbar', () => {
    renderChart();
    fireEvent.click(screen.getByRole('button', { name: '5D' }));
    expect(runtime.setChartVisibleRange).toHaveBeenCalledTimes(1);
    expect(runtime.setChartVisibleRange.mock.calls[0][0]).toMatch(/^kite-chart-/);
    expect(runtime.setChartVisibleRange.mock.calls[0][1]).toBe('5D');
  });

  it('registers fresh candle context and removes it on unmount', () => {
    const { unmount } = renderChart();
    expect(runtime.setChartParityContext).toHaveBeenCalledWith(expect.objectContaining({
      symbol: 'NSE:RELIANCE', tf: '15m', rawCandles: candles,
    }));
    const id = runtime.setChartParityContext.mock.calls[0][0].id;
    unmount();
    expect(runtime.removeChartParityContext).toHaveBeenCalledWith(id);
  });

  it('hides the recognized duplicate InstrumentPane header', () => {
    render(withQueryClient(
      <div>
        <div data-testid="legacy-header">RELIANCE 2 bars</div>
        <div>
          <TradingViewKiteChart
            symbol="NSE:RELIANCE"
            rawCandles={candles}
            tf="15m"
            theme={theme}
            activeIndicators={new Set(['st-mid'])}
            params={{}}
          />
        </div>
      </div>,
    ));
    expect(screen.getByTestId('legacy-header').style.display).toBe('none');
  });

  it('uses dark shell styling when the chart is dark', () => {
    const { container } = renderChart({ isDark: true });
    expect(container.querySelector('.sterling-zerodha-chart')?.classList.contains('is-dark')).toBe(true);
  });
});
