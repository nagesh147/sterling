import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

const useCandlesMock = vi.hoisted(() => vi.fn((..._args: any[]) => ({ data: [] })));
const createChartMock = vi.hoisted(() => vi.fn());

vi.mock('../../../hooks/useCandles', () => ({ useCandles: (...args: any[]) => useCandlesMock(...args) }));
vi.mock('../../../hooks/useAlerts', () => ({
  useCreateAlert: () => ({ mutate: vi.fn(), isPending: false, isError: false, error: null }),
}));
vi.mock('../../../hooks/useKiteDrawings', () => ({
  useKiteDrawings: () => ({
    drawMode: 'crosshair', setDrawMode: vi.fn(), drawingPoints: [], setDrawingPoints: vi.fn(),
    selectedDrawingId: null, setSelectedDrawingId: vi.fn(), isDragging: false,
    onMouseDown: vi.fn(), onMouseMove: vi.fn(), onMouseUp: vi.fn(), handleChartClick: vi.fn(),
    clearDrawings: vi.fn(), snapToOHLC: (price: number) => price, updateDrawingText: vi.fn(),
    setDrawings: vi.fn(), undo: vi.fn(), redo: vi.fn(),
  }),
}));
vi.mock('../MiniGridPane', () => ({ MiniGridPane: () => null }));
vi.mock('lightweight-charts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('lightweight-charts')>();
  return { ...actual, createChart: (...args: any[]) => createChartMock(...args), createSeriesMarkers: vi.fn() };
});

import { TradingViewKiteChart } from '../TradingViewKiteChart';

const theme = {
  bg: '#fff', surface: '#f7f7f7', border: '#ddd', text: '#111', dim: '#777',
  blue: '#2962ff', red: '#e05260', green: '#2db784', amber: '#ff9800',
  orange: '#ff6d00', cyan: '#00bcd4', purple: '#ab47bc', fontFamily: 'sans-serif',
};

function renderChart(overrides: Record<string, unknown> = {}) {
  return render(
    <TradingViewKiteChart
      symbol="NSE:RELIANCE"
      rawCandles={[]}
      tf="15m"
      theme={theme}
      activeIndicators={new Set(['vol'])}
      params={{}}
      {...overrides}
    />,
  );
}

describe('TradingViewKiteChart workspace controls', () => {
  const chartInstances: any[] = [];

  beforeEach(() => {
    localStorage.clear();
    useCandlesMock.mockReturnValue({ data: [] });
    createChartMock.mockClear();
    chartInstances.length = 0;
    class ResizeObserverMock { observe() {} disconnect() {} }
    vi.stubGlobal('ResizeObserver', ResizeObserverMock);
    createChartMock.mockImplementation(() => {
      const series = () => ({
        setData: vi.fn(), applyOptions: vi.fn(), createPriceLine: vi.fn(() => ({})),
        priceToCoordinate: vi.fn(() => 100), coordinateToPrice: vi.fn(() => 100),
      });
      const timeScale = {
        fitContent: vi.fn(), setVisibleRange: vi.fn(), getVisibleRange: vi.fn(() => null),
        getVisibleLogicalRange: vi.fn(() => ({ from: 0, to: 50 })), setVisibleLogicalRange: vi.fn(),
        subscribeVisibleTimeRangeChange: vi.fn(), unsubscribeVisibleTimeRangeChange: vi.fn(),
        coordinateToLogical: vi.fn(() => 1), timeToCoordinate: vi.fn(() => 1),
        options: vi.fn(() => ({ barSpacing: 6 })), applyOptions: vi.fn(),
      };
      const priceScale = { applyOptions: vi.fn(), width: vi.fn(() => 56), options: vi.fn(() => ({ autoScale: true })) };
      const chart = {
        addSeries: vi.fn(series), timeScale: vi.fn(() => timeScale), priceScale: vi.fn(() => priceScale),
        subscribeCrosshairMove: vi.fn(), subscribeClick: vi.fn(), applyOptions: vi.fn(), remove: vi.fn(),
      };
      chartInstances.push(chart);
      return chart;
    });
  });

  it('adds a custom formula instance from the indicator dialog', () => {
    renderChart();
    fireEvent.click(screen.getByRole('button', { name: /fx Indicators/i }));
    fireEvent.click(screen.getByRole('button', { name: /\+ Formula/i }));
    expect(screen.getByDisplayValue('hlc3')).toBeTruthy();
  });

  it('saves a named template containing the current chart state', () => {
    renderChart();
    fireEvent.click(screen.getByTitle('Save or apply chart template'));
    fireEvent.change(screen.getByPlaceholderText('Template name'), { target: { value: 'Momentum desk' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save current' }));
    const saved = JSON.parse(localStorage.getItem('sterling:kite-chart-templates:v1') || '[]');
    expect(saved[0].name).toBe('Momentum desk');
    expect(saved[0].snapshot.activeIndicators).toEqual(['vol']);
  });

  it('opens the replay/date workflow from the chart toolbar', () => {
    renderChart();
    fireEvent.click(screen.getByTitle('Go to date or start bar replay'));
    expect(screen.getByText('Go to date / Bar Replay')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Start replay' }).hasAttribute('disabled')).toBe(true);
  });

  it('starts replay with progress and speed controls', () => {
    const bars = Array.from({ length: 80 }, (_, index) => ({ time: index + 1, open: 100 + index, high: 102 + index, low: 99 + index, close: 101 + index, volume: 1000 + index }));
    renderChart({ rawCandles: bars });
    fireEvent.click(screen.getByTitle('Go to date or start bar replay'));
    fireEvent.change(screen.getByLabelText('Replay speed'), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Start replay' }));
    expect(screen.getByLabelText('Replay progress')).toBeTruthy();
    expect(screen.getByLabelText('Replay speed')).toBeTruthy();
  });

  it('imports and exports templates as normalized JSON', () => {
    renderChart();
    fireEvent.click(screen.getByTitle('Save or apply chart template'));
    fireEvent.change(screen.getByPlaceholderText('Template name'), { target: { value: 'Momentum desk' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save current' }));
    fireEvent.click(screen.getByRole('button', { name: 'Export JSON' }));
    expect((screen.getByPlaceholderText('Paste or export template JSON') as HTMLTextAreaElement).value).toContain('"Momentum desk"');

    const imported = JSON.stringify({
      templates: [{
        id: 'imported',
        name: 'Imported layout',
        createdAt: 1,
        snapshot: {
          tf: '5m',
          chartType: 'line',
          layoutMode: '1',
          isHA: false,
          isLogScale: false,
          showVP: false,
          activeIndicators: ['ema', 'ema'],
          params: {},
          workspace: { styles: {}, extraIndicators: [], compareSymbol: 'nse:tcs', appearance: {} },
        },
      }],
    });
    fireEvent.change(screen.getByPlaceholderText('Paste or export template JSON'), { target: { value: imported } });
    fireEvent.click(screen.getByRole('button', { name: 'Import JSON' }));
    const saved = JSON.parse(localStorage.getItem('sterling:kite-chart-templates:v1') || '[]');
    expect(saved.some((template: any) => template.name === 'Imported layout')).toBe(true);
  });

  it('manages multiple comparison overlays', async () => {
    renderChart();
    fireEvent.click(screen.getByTitle('Compare another symbol'));

    const input = screen.getByPlaceholderText('NSE:TCS');
    fireEvent.change(input, { target: { value: 'NSE:TCS' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    fireEvent.change(screen.getByLabelText('NSE:TCS comparison mode'), { target: { value: 'price' } });

    fireEvent.change(input, { target: { value: 'NSE:INFY' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    expect(screen.getByLabelText('NSE:INFY visible')).toBeTruthy();

    await waitFor(() => {
      const saved = JSON.parse(localStorage.getItem('sterling:kite-chart-workspace:v1') || '{}');
      expect(saved.comparisons.map((overlay: any) => overlay.symbol)).toEqual(['NSE:TCS', 'NSE:INFY']);
      expect(saved.comparisons[0].mode).toBe('price');
    });
  });

  it('builds the complete indicator roster, duplicates, formulas, and comparison series', async () => {
    localStorage.setItem('sterling:kite-chart-workspace:v1', JSON.stringify({
      styles: {},
      compareSymbol: 'NSE:TCS',
      appearance: { candleUp: '#2db784', candleDown: '#e05260', gridVisible: true, magnetCrosshair: true },
      extraIndicators: [
        { id: 'ema-2', kind: 'ema', name: 'EMA', period: 34, style: { color: '#123456', lineWidth: 2, visible: true } },
        { id: 'formula-1', kind: 'formula', name: 'Typical', period: 1, formula: 'hlc3', style: { color: '#654321', lineWidth: 2, visible: true } },
      ],
    }));
    const bars = Array.from({ length: 60 }, (_, index) => ({ time: index + 1, open: 100 + index, high: 102 + index, low: 99 + index, close: 101 + index, volume: 1000 + index }));
    useCandlesMock.mockReturnValue({ data: bars });
    renderChart({ rawCandles: bars, activeIndicators: new Set(['ema', 'bb', 'st-fast', 'st-mid', 'st-slow', 'vwap', 'vol', 'rsi', 'macd', 'sma', 'atr', 'stoch']) });
    await waitFor(() => expect(createChartMock).toHaveBeenCalledTimes(3));
    expect(chartInstances[0].addSeries.mock.calls.length).toBeGreaterThanOrEqual(17);
  });
});
