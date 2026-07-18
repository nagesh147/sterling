import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import React from 'react';

/**
 * Regression lock for the "switch loader" (2026-07-18): a chart switch (new
 * symbol/timeframe) must show a loading overlay from the moment the switch
 * starts until the chart has ACTUALLY finished its rebuild - not just when
 * candle data has arrived, since createChart()+indicator recompute is the
 * expensive part that used to leave the UI looking frozen with no feedback.
 */

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
const B = 'NSE:BBB';
const LOADING_TEXT = 'Loading chart…';

describe('InstrumentPane chart-switch loader', () => {
  beforeEach(() => {
    chartProps = null;
    __resetGlobalChartStateCache();
    apiGet.mockReset();
    apiGet.mockResolvedValue({});
    apiPost.mockClear();
    useCandlesMock.mockReset();
    useCandlesMock.mockReturnValue({ data: [], isLoading: false });
    vi.useRealTimers();
  });

  it('shows the loader while candles are still loading for a fresh symbol', async () => {
    useCandlesMock.mockReturnValue({ data: [], isLoading: true });
    render(<InstrumentPane symbol={A} />);
    await waitFor(() => expect(chartProps).toBeTruthy());
    expect(screen.getByText(LOADING_TEXT)).toBeTruthy();
  });

  it('hides the loader once candles arrive and the chart signals it finished rendering', async () => {
    useCandlesMock.mockReturnValue({ data: [], isLoading: true });
    const { rerender } = render(<InstrumentPane symbol={A} />);
    await waitFor(() => expect(chartProps).toBeTruthy());
    expect(screen.getByText(LOADING_TEXT)).toBeTruthy();

    // Candles arrive.
    useCandlesMock.mockReturnValue({ data: [{ time: 1, open: 1, high: 1, low: 1, close: 1, volume: 1 }], isLoading: false });
    await act(async () => { rerender(<InstrumentPane symbol={A} />); });
    // Still loading: data arrived but the chart hasn't finished its rebuild yet.
    expect(screen.getByText(LOADING_TEXT)).toBeTruthy();

    // Chart finishes its (expensive) rebuild and calls back.
    await act(async () => { chartProps.onChartReady(); });
    expect(screen.queryByText(LOADING_TEXT)).toBeNull();
  });

  it('re-shows the loader on a symbol switch even when the new symbol is already cached', async () => {
    useCandlesMock.mockReturnValue({ data: [{ time: 1, open: 1, high: 1, low: 1, close: 1, volume: 1 }], isLoading: false });
    const { rerender } = render(<InstrumentPane symbol={A} />);
    await waitFor(() => expect(chartProps).toBeTruthy());
    await act(async () => { chartProps.onChartReady(); });
    expect(screen.queryByText(LOADING_TEXT)).toBeNull();

    // Switch to B - data is instantly available (cached), but the structural
    // chart rebuild still needs to happen; the loader must reappear regardless.
    await act(async () => { rerender(<InstrumentPane symbol={B} />); });
    expect(screen.getByText(LOADING_TEXT)).toBeTruthy();

    await act(async () => { chartProps.onChartReady(); });
    expect(screen.queryByText(LOADING_TEXT)).toBeNull();
  });

  it('keeps the loader up while useCandles is still serving the OUTGOING symbol as placeholder data (keepPreviousData)', async () => {
    // The app-wide QueryClient default is `placeholderData: keepPreviousData`
    // (App.tsx), so on a genuine symbol switch useCandles reports isLoading:false
    // and still-the-old-symbol's data as a "placeholder" for the new query key -
    // isPlaceholderData is the only flag that's true during that window. If the
    // loader ignored it, the chart would finish its structural rebuild using the
    // stale placeholder candles and call onChartReady, revealing what looks
    // exactly like the outgoing symbol's chart under the new symbol's label.
    const staleData = [{ time: 1, open: 1, high: 1, low: 1, close: 1, volume: 1 }];
    useCandlesMock.mockReturnValue({ data: staleData, isLoading: false, isPlaceholderData: false });
    const { rerender } = render(<InstrumentPane symbol={A} />);
    await waitFor(() => expect(chartProps).toBeTruthy());
    await act(async () => { chartProps.onChartReady(); });
    expect(screen.queryByText(LOADING_TEXT)).toBeNull();

    // Switch to B - react-query hands back A's stale candles as a placeholder.
    useCandlesMock.mockReturnValue({ data: staleData, isLoading: false, isPlaceholderData: true });
    await act(async () => { rerender(<InstrumentPane symbol={B} />); });
    expect(screen.getByText(LOADING_TEXT)).toBeTruthy();

    // The structural rebuild finishes (using the stale placeholder data) and
    // calls back - the loader must stay up regardless, since the data on
    // screen still isn't B's.
    await act(async () => { chartProps.onChartReady(); });
    expect(screen.getByText(LOADING_TEXT)).toBeTruthy();

    // B's real data lands - only now may the loader clear.
    const freshData = [{ time: 1, open: 1, high: 1, low: 1, close: 1, volume: 1 }, { time: 2, open: 1, high: 1, low: 1, close: 1, volume: 1 }];
    useCandlesMock.mockReturnValue({ data: freshData, isLoading: false, isPlaceholderData: false });
    await act(async () => { rerender(<InstrumentPane symbol={B} />); });
    expect(screen.queryByText(LOADING_TEXT)).toBeNull();
  });

  it('does not get stuck forever if the chart never signals ready (safety timeout)', async () => {
    vi.useFakeTimers();
    // Candles are already available - isolates the case under test (the
    // structural rebuild itself hangs / never calls onChartReady) from the
    // separate, legitimate "still waiting on the network" loading state.
    useCandlesMock.mockReturnValue({ data: [{ time: 1, open: 1, high: 1, low: 1, close: 1, volume: 1 }], isLoading: false });
    render(<InstrumentPane symbol={A} />);
    await act(async () => { await Promise.resolve(); });
    expect(chartProps).toBeTruthy();
    expect(screen.getByText(LOADING_TEXT)).toBeTruthy();

    await act(async () => { vi.advanceTimersByTime(6000); });
    expect(screen.queryByText(LOADING_TEXT)).toBeNull();
    vi.useRealTimers();
  });
});
