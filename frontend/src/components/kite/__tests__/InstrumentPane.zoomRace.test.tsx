import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, waitFor } from '@testing-library/react';
import React from 'react';

/**
 * Regression lock for the "loads at one zoom, snaps to another a split second
 * later" bug (2026-07-18): on a cold mount, `persistedZoom` starts null (no
 * saved zoom known yet) while the chart-state GET is in flight. If the chart
 * mounts immediately it default-fits, then rebuilds moments later once the
 * GET resolves with the real saved zoom - a visible zoom-level flash. The
 * fix withholds the chart's first mount until the saved zoom is known
 * (zoomResolved), so the very first createChart() already has the right range.
 */

let chartMounts: any[] = [];
vi.mock('../../charts/TradingViewKiteChart', () => ({
  TradingViewKiteChart: (props: any) => {
    chartMounts.push(props);
    return React.createElement('div', { 'data-testid': 'tvchart' });
  },
}));

const useCandlesMock = vi.fn();
vi.mock('../../../hooks/useCandles', () => ({ useCandles: (...args: any[]) => useCandlesMock(...args) }));
vi.mock('../../../hooks/useKite', () => ({ useKitePositions: () => ({ data: null }) }));
vi.mock('../../../hooks/useKiteOptionChain', () => ({ useKiteOptionChain: () => ({ data: null }) }));
// The Navigator chart overlay only fetches when one of its indicators is on;
// these tests render without a QueryClientProvider, so stub the hook out.
vi.mock('../../../hooks/useNavigator', () => ({ useNavigatorChart: () => ({ data: null, isLoading: false, error: null }) }));
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

let resolveGet: (v: any) => void;
const apiGet = vi.fn<[string], Promise<any>>(() => new Promise((res) => { resolveGet = res; }));
const apiPost = vi.fn<[string, any?, any?], Promise<any>>(() => Promise.resolve({}));
vi.mock('../../../utils/api', () => ({
  api: {
    get: (url: string) => apiGet(url),
    post: (url: string, body?: any, opts?: any) => apiPost(url, body, opts),
  },
}));

import { InstrumentPane, __resetGlobalChartStateCache } from '../InstrumentPane';

const A = 'NSE:AAA';
const SAVED_ZOOM = { from: 100, to: 200 };

describe('InstrumentPane cold-mount zoom race', () => {
  beforeEach(() => {
    chartMounts = [];
    __resetGlobalChartStateCache();
    apiGet.mockClear();
    apiPost.mockClear();
    useCandlesMock.mockReset();
    // Candles already available - isolates the case under test (the zoom GET
    // still in flight) from the separate candle-loading state.
    useCandlesMock.mockReturnValue({ data: [{ time: 1, open: 1, high: 1, low: 1, close: 1, volume: 1 }], isLoading: false });
  });

  it('does not mount the chart before the saved-zoom GET resolves', async () => {
    render(<InstrumentPane symbol={A} />);
    await act(async () => { await Promise.resolve(); });
    // GET is still pending - the chart must not have mounted yet (that mount
    // is what used to default-fit before the real zoom arrived).
    expect(chartMounts.length).toBe(0);
    expect(screen.getByText('Loading chart…')).toBeTruthy();
  });

  it('does not let a slow chart-state GET block first paint for more than the soft timeout', async () => {
    vi.useFakeTimers();
    const { unmount } = render(<InstrumentPane symbol={A} />);
    await act(async () => { await Promise.resolve(); });
    expect(chartMounts.length).toBe(0);

    await act(async () => { vi.advanceTimersByTime(449); });
    expect(chartMounts.length).toBe(0);

    await act(async () => { vi.advanceTimersByTime(1); });
    expect(chartMounts.length).toBe(1);
    expect(chartMounts[0].persistedZoom).toBeNull();

    unmount();
    vi.useRealTimers();
  });

  it('mounts the chart exactly once, already carrying the resolved zoom - no fit-then-snap', async () => {
    render(<InstrumentPane symbol={A} />);
    await act(async () => { await Promise.resolve(); });
    expect(chartMounts.length).toBe(0);

    await act(async () => { resolveGet({ zoom: SAVED_ZOOM }); await Promise.resolve(); await Promise.resolve(); });

    // Exactly one mount, and its persistedZoom is the real saved value from
    // the very first render - never null first, then corrected.
    expect(chartMounts.length).toBe(1);
    expect(chartMounts[0].persistedZoom).toEqual(SAVED_ZOOM);
  });

  it('still mounts the chart (with no saved zoom) if the GET fails', async () => {
    const rejecting = vi.fn<[string], Promise<any>>(() => Promise.reject(new Error('network down')));
    apiGet.mockImplementationOnce(rejecting as any);
    render(<InstrumentPane symbol={A} />);
    await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
    expect(chartMounts.length).toBe(1);
    expect(chartMounts[0].persistedZoom).toBeNull();
  });
});
