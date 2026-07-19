import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, waitFor } from '@testing-library/react';
import React from 'react';

let chartProps: any = null;
vi.mock('../../charts/TradingViewKiteChart', () => ({
  TradingViewKiteChart: (props: any) => {
    chartProps = props;
    return React.createElement('div', { 'data-testid': 'tvchart' });
  },
}));

const useCandlesMock = vi.fn();
vi.mock('../../../hooks/useCandles', () => ({ useCandles: (...args: any[]) => useCandlesMock(...args) }));
vi.mock('../../../hooks/useKite', () => ({ useKitePositions: () => ({ data: null }) }));
vi.mock('../../../hooks/useKiteOptionChain', () => ({ useKiteOptionChain: () => ({ data: null }) }));
vi.mock('../../../store/useOrderWindowStore', () => ({
  useOrderWindowStore: (sel?: any) =>
    (sel ? sel({ openOrderWindow: vi.fn() }) : { openOrderWindow: vi.fn() }),
}));
vi.mock('../../../hooks/useKiteDrawings', () => ({
  useKiteDrawings: () => ({
    drawings: [], setDrawings: vi.fn(), drawMode: 'crosshair', setDrawMode: vi.fn(),
    drawingPoints: [], setDrawingPoints: vi.fn(), selectedDrawingId: null,
    setSelectedDrawingId: vi.fn(), isDragging: false, clearDrawings: vi.fn(),
  }),
}));

const apiGet = vi.fn<[string], Promise<any>>();
const apiPost = vi.fn<[string, any?, any?], Promise<any>>(() => Promise.resolve({}));
vi.mock('../../../utils/api', () => ({
  api: {
    get: (url: string) => apiGet(url),
    post: (url: string, body?: any, opts?: any) => apiPost(url, body, opts),
  },
}));

import { InstrumentPane, __resetGlobalChartStateCache } from '../InstrumentPane';

const A = 'NSE:AAA';
const LOCAL_CHART_STATE_KEY = 'sterling:kite-chart-state:__global__:v1';
const candles = [
  { time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 100 },
  { time: 2, open: 1.5, high: 2.5, low: 1, close: 2, volume: 120 },
];

describe('InstrumentPane chart end-to-end flows', () => {
  beforeEach(() => {
    chartProps = null;
    localStorage.clear();
    __resetGlobalChartStateCache();
    apiGet.mockReset();
    apiGet.mockResolvedValue({});
    apiPost.mockClear();
    useCandlesMock.mockReset();
    useCandlesMock.mockReturnValue({ data: candles, isLoading: false, isPlaceholderData: false });
    vi.useRealTimers();
  });

  it('fast-starts from the local chart-state cache without waiting for backend state', async () => {
    const cachedState = {
      zoom: { from: 10, to: 20 },
      drawingsBySymbol: {},
      tf: '1H',
      active: ['vol', 'rsi'],
      isHA: true,
      isLogScale: true,
      showVP: true,
      params: { rsiPeriod: 9 },
    };
    localStorage.setItem(LOCAL_CHART_STATE_KEY, JSON.stringify(cachedState));

    render(<InstrumentPane symbol={A} />);
    await waitFor(() => expect(chartProps).toBeTruthy());

    expect(apiGet).not.toHaveBeenCalled();
    expect(chartProps.tf).toBe('1H');
    expect(chartProps.isHA).toBe(true);
    expect(chartProps.isLogScale).toBe(true);
    expect(chartProps.showVP).toBe(true);
    expect(chartProps.persistedZoom).toEqual(cachedState.zoom);
    expect(Array.from(chartProps.activeIndicators)).toEqual(['vol', 'rsi']);
    expect(chartProps.params.rsiPeriod).toBe(9);
  });

  it('does not let a late chart-state response overwrite a user timeframe change after soft timeout', async () => {
    vi.useFakeTimers();
    let resolveGet: (value: any) => void = () => {};
    apiGet.mockImplementation(() => new Promise((resolve) => { resolveGet = resolve; }));

    const { unmount } = render(<InstrumentPane symbol={A} />);
    await act(async () => { await Promise.resolve(); });
    expect(chartProps).toBeNull();

    await act(async () => { vi.advanceTimersByTime(450); });
    expect(chartProps.tf).toBe('15m');

    await act(async () => { chartProps.onTfChange('1H'); });
    expect(chartProps.tf).toBe('1H');

    await act(async () => {
      resolveGet({
        zoom: { from: 100, to: 200 },
        drawingsBySymbol: {},
        tf: '5m',
        active: ['rsi'],
        isHA: true,
        isLogScale: true,
        showVP: true,
        params: { rsiPeriod: 99 },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(chartProps.tf).toBe('1H');
    expect(chartProps.isHA).toBe(false);
    expect(Array.from(chartProps.activeIndicators)).toEqual(['vol', 'st-mid']);

    await act(async () => { unmount(); });
    const lastSave = apiPost.mock.calls[apiPost.mock.calls.length - 1];
    expect(lastSave?.[1].tf).toBe('1H');
    expect(JSON.parse(localStorage.getItem(LOCAL_CHART_STATE_KEY) || '{}').tf).toBe('1H');
    vi.useRealTimers();
  });

  it('updates the local fast-start cache when chart config is saved', async () => {
    const { unmount } = render(<InstrumentPane symbol={A} />);
    await waitFor(() => expect(chartProps).toBeTruthy());
    await act(async () => { chartProps.onChartReady(`${A}|15m|2|1|2`); });

    await act(async () => { chartProps.onTfChange('4H'); });
    await act(async () => { unmount(); });

    const cached = JSON.parse(localStorage.getItem(LOCAL_CHART_STATE_KEY) || '{}');
    expect(cached.tf).toBe('4H');
    expect(apiPost.mock.calls[apiPost.mock.calls.length - 1]?.[1].tf).toBe('4H');
  });
});
