import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, waitFor } from '@testing-library/react';
import React from 'react';

/**
 * Regression lock for "chart changes not getting persisted when switching symbols".
 *
 * Chart state (timeframe, indicators, drawings, toggles, params) is saved to the
 * backend with a 700ms debounce keyed on a single shared timeout ref. Switching
 * symbols within that window used to DROP the outgoing symbol's pending save:
 *   (a) the incoming symbol's load schedules its own save, whose clearTimeout
 *       cancels the still-pending one (mode-independent), and
 *   (b) in Mac motion mode MacSectionFade remounts the pane on switch, and the
 *       unmount cleanup cleared the timer.
 * The fix flushes (immediately POSTs) the outgoing symbol's pending save on both
 * the symbol-change effect and unmount. These tests assert the flush happens
 * WITHOUT advancing the 700ms timer, i.e. the change is not lost.
 */

// Capture the props InstrumentPane passes into the (heavy, canvas-based) chart so
// the test can drive user changes (onTfChange) without a real lightweight-charts.
let chartProps: any = null;
vi.mock('../../charts/TradingViewKiteChart', () => ({
  TradingViewKiteChart: (props: any) => {
    chartProps = props;
    return React.createElement('div', { 'data-testid': 'tvchart' });
  },
}));

vi.mock('../../../hooks/useCandles', () => ({ useCandles: () => ({ data: [] }) }));
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
    // Capture the 3rd (transport-options) arg so tests can assert the unload
    // path uses a keepalive-capable transport.
    post: (url: string, body?: any, opts?: any) => apiPost(url, body, opts),
  },
}));

import { InstrumentPane } from '../InstrumentPane';

const A = 'NSE:AAA';
const B = 'NSE:BBB';
const encA = encodeURIComponent(A); // NSE%3AAAA

async function renderLoaded(symbol: string) {
  const utils = render(<InstrumentPane symbol={symbol} />);
  await waitFor(() => expect(chartProps).toBeTruthy());
  await waitFor(() =>
    expect(apiGet).toHaveBeenCalledWith(expect.stringContaining(encodeURIComponent(symbol)))
  );
  // Flush the resolved GET + the setChartStateLoaded(true) it triggers so that
  // subsequent user changes actually schedule saves.
  await act(async () => {});
  return utils;
}

function savesFor(symbol: string) {
  const enc = encodeURIComponent(symbol);
  return apiPost.mock.calls.filter(([url]: any[]) => String(url).includes(enc));
}

describe('InstrumentPane chart-state persistence across symbol switch', () => {
  beforeEach(() => {
    chartProps = null;
    apiGet.mockReset();
    apiGet.mockResolvedValue({}); // empty defaults
    apiPost.mockClear();
  });

  it('flushes the outgoing symbol’s pending save when switching to another symbol', async () => {
    const { rerender } = await renderLoaded(A);
    apiPost.mockClear(); // ignore any load-time save for A

    // User changes timeframe on A (schedules a debounced save).
    await act(async () => { chartProps.onTfChange('1H'); });

    // Switch to B well within the 700ms window (no timers advanced).
    await act(async () => { rerender(<InstrumentPane symbol={B} />); });

    const aSaves = savesFor(A);
    expect(aSaves.length).toBeGreaterThan(0);
    expect(aSaves[aSaves.length - 1][1].tf).toBe('1H');
    expect(String(aSaves[aSaves.length - 1][0])).toContain(encA);
  });

  it('flushes the pending save on unmount (Mac-mode MacSectionFade remount path)', async () => {
    const { unmount } = await renderLoaded(A);
    apiPost.mockClear();

    await act(async () => { chartProps.onTfChange('4H'); });
    await act(async () => { unmount(); });

    const aSaves = savesFor(A);
    expect(aSaves.length).toBeGreaterThan(0);
    expect(aSaves[aSaves.length - 1][1].tf).toBe('4H');
  });

  it('preserves the loaded zoom on a non-zoom save (does not clobber it with null)', async () => {
    // The backend does a full replace, so a config/drawing save that omits zoom
    // would persist zoom:null and wipe the stored range. The loaded zoom is
    // seeded into lastZoomRef and used as the save default.
    const ZOOM = { from: 1700000000, to: 1700360000 };
    apiGet.mockResolvedValue({ zoom: ZOOM });
    const { unmount } = await renderLoaded(A);
    apiPost.mockClear();

    // A non-zoom change (timeframe) followed by a flush.
    await act(async () => { chartProps.onTfChange('1H'); });
    await act(async () => { unmount(); });

    const aSaves = savesFor(A);
    expect(aSaves.length).toBeGreaterThan(0);
    expect(aSaves[aSaves.length - 1][1].zoom).toEqual(ZOOM);
  });

  it('resets params to defaults on symbol switch (no leak from previous symbol)', async () => {
    const { rerender, unmount } = await renderLoaded(A);

    // Modify a param on A, then switch to B (whose stored state has no params).
    await act(async () => { chartProps.onParamsChange({ ...chartProps.params, rsiPeriod: 99 }); });
    await act(async () => { rerender(<InstrumentPane symbol={B} />); });
    await waitFor(() =>
      expect(apiGet).toHaveBeenCalledWith(expect.stringContaining(encodeURIComponent(B)))
    );
    await act(async () => {}); // B's load resolves → chartStateLoaded true
    apiPost.mockClear();

    // A user change on B, flushed: its params must be B's defaults, not A's 99.
    await act(async () => { chartProps.onTfChange('1H'); });
    await act(async () => { unmount(); });

    const bSaves = savesFor(B);
    expect(bSaves.length).toBeGreaterThan(0);
    expect(bSaves[bSaves.length - 1][1].params.rsiPeriod).toBe(14);
  });

  it('flushes the pending save on a hard page unload (pagehide) via a keepalive transport', async () => {
    // A hard unload - tab close, refresh, or browser navigation - does NOT run
    // React unmount, so neither the symbol-switch nor the unmount flush fires. A
    // pagehide listener must flush the pending save, and because a normal fetch is
    // cancelled by the unload it must use a keepalive-capable transport.
    const { unmount } = await renderLoaded(A);
    apiPost.mockClear();

    // User change well within the 700ms debounce window (schedules a pending save).
    await act(async () => { chartProps.onTfChange('1H'); });

    // Simulate the tab closing / page unloading. No timers advanced, no unmount.
    await act(async () => { window.dispatchEvent(new Event('pagehide')); });

    const aSaves = savesFor(A);
    expect(aSaves.length).toBeGreaterThan(0);
    const last = aSaves[aSaves.length - 1];
    expect(last[1].tf).toBe('1H');              // the just-made change reached the endpoint
    expect(last[2]).toEqual({ keepalive: true }); // via the unload-safe transport

    unmount();
  });
});
