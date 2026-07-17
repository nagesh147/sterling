import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, waitFor } from '@testing-library/react';
import React from 'react';

/**
 * Regression lock for the Kite chart-state persistence, reworked to a GLOBAL
 * config model (2026-07-18).
 *
 * Chart config (timeframe, indicators, params, toggles, zoom) is now shared
 * across EVERY symbol - switching symbols must KEEP the same view ("same
 * throughout"), not reset to per-symbol defaults. Only drawing geometry stays
 * keyed by symbol, carried inside one global blob under `drawingsBySymbol`.
 * Persistence is a single blob under the `__global__` key with the existing
 * debounce / flush-on-unmount / pagehide-keepalive machinery.
 *
 * These tests assert: config survives a symbol switch, saves target the global
 * key, zoom is preserved on non-zoom saves AND carried to the next symbol, and
 * the unload paths still flush.
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

import { InstrumentPane, __resetGlobalChartStateCache } from '../InstrumentPane';

const A = 'NSE:AAA';
const B = 'NSE:BBB';
const GLOBAL = '__global__';

async function renderLoaded(symbol: string) {
  const utils = render(<InstrumentPane symbol={symbol} />);
  await waitFor(() => expect(chartProps).toBeTruthy());
  // Cold mount fetches the single global blob (not a per-symbol key).
  await waitFor(() => expect(apiGet).toHaveBeenCalledWith(expect.stringContaining(GLOBAL)));
  // Flush the resolved GET + the setChartStateLoaded(true) it triggers so that
  // subsequent user changes actually schedule saves.
  await act(async () => {});
  return utils;
}

function globalSaves() {
  return apiPost.mock.calls.filter(([url]: any[]) => String(url).includes(GLOBAL));
}

describe('InstrumentPane global chart-state persistence', () => {
  beforeEach(() => {
    chartProps = null;
    __resetGlobalChartStateCache(); // each test starts with a cold session cache
    apiGet.mockReset();
    apiGet.mockResolvedValue({}); // empty defaults
    apiPost.mockClear();
  });

  it('keeps config the same across a symbol switch (global, not reset)', async () => {
    const { rerender } = await renderLoaded(A);

    // User changes timeframe while viewing A.
    await act(async () => { chartProps.onTfChange('1H'); });
    expect(chartProps.tf).toBe('1H');

    // Switch to B: config must be RETAINED (the old code reset it to '15m').
    await act(async () => { rerender(<InstrumentPane symbol={B} />); });
    expect(chartProps.tf).toBe('1H');
  });

  it('persists to the shared global key, never a per-symbol key', async () => {
    const { unmount } = await renderLoaded(A);
    apiPost.mockClear();

    await act(async () => { chartProps.onTfChange('4H'); });
    await act(async () => { unmount(); });

    const saves = globalSaves();
    expect(saves.length).toBeGreaterThan(0);
    // Every save hit the global key, and none targeted the symbol.
    for (const [url] of apiPost.mock.calls) {
      expect(String(url)).toContain(GLOBAL);
      expect(String(url)).not.toContain(encodeURIComponent(A));
    }
    expect(saves[saves.length - 1][1].tf).toBe('4H');
  });

  it('preserves the loaded zoom on a non-zoom save (does not clobber with null)', async () => {
    // The backend does a full replace, so a config save that omits zoom would
    // persist zoom:null. The loaded zoom is seeded into lastZoomRef and reused.
    const ZOOM = { from: 1700000000, to: 1700360000 };
    apiGet.mockResolvedValue({ zoom: ZOOM });
    const { unmount } = await renderLoaded(A);
    apiPost.mockClear();

    await act(async () => { chartProps.onTfChange('1H'); });
    await act(async () => { unmount(); });

    const saves = globalSaves();
    expect(saves.length).toBeGreaterThan(0);
    expect(saves[saves.length - 1][1].zoom).toEqual(ZOOM);
  });

  it('carries the current zoom to the next symbol on switch (same window throughout)', async () => {
    const ZOOM = { from: 1700000000, to: 1700360000 };
    apiGet.mockResolvedValue({ zoom: ZOOM });
    const { rerender } = await renderLoaded(A);
    expect(chartProps.persistedZoom).toEqual(ZOOM);

    // Switching symbols must keep the same visible window, not clear it.
    await act(async () => { rerender(<InstrumentPane symbol={B} />); });
    expect(chartProps.persistedZoom).toEqual(ZOOM);
  });

  it('keeps indicator params across a symbol switch (no reset to defaults)', async () => {
    const { rerender } = await renderLoaded(A);

    await act(async () => { chartProps.onParamsChange({ ...chartProps.params, rsiPeriod: 99 }); });
    expect(chartProps.params.rsiPeriod).toBe(99);

    await act(async () => { rerender(<InstrumentPane symbol={B} />); });
    // Global config: the param stays 99 instead of resetting to the default 14.
    expect(chartProps.params.rsiPeriod).toBe(99);
  });

  it('flushes the pending save on unmount (Mac-mode MacSectionFade remount path)', async () => {
    const { unmount } = await renderLoaded(A);
    apiPost.mockClear();

    await act(async () => { chartProps.onTfChange('4H'); });
    await act(async () => { unmount(); });

    const saves = globalSaves();
    expect(saves.length).toBeGreaterThan(0);
    expect(saves[saves.length - 1][1].tf).toBe('4H');
  });

  it('flushes the pending save on a hard page unload (pagehide) via a keepalive transport', async () => {
    const { unmount } = await renderLoaded(A);
    apiPost.mockClear();

    // User change well within the 700ms debounce window (schedules a pending save).
    await act(async () => { chartProps.onTfChange('1H'); });

    // Simulate the tab closing / page unloading. No timers advanced, no unmount.
    await act(async () => { window.dispatchEvent(new Event('pagehide')); });

    const saves = globalSaves();
    expect(saves.length).toBeGreaterThan(0);
    const last = saves[saves.length - 1];
    expect(last[1].tf).toBe('1H');               // the just-made change reached the endpoint
    expect(last[2]).toEqual({ keepalive: true }); // via the unload-safe transport

    unmount();
  });

  it('does NOT persist over saved state when the load GET fails (no default clobber)', async () => {
    // The backend POST is a full replace. If a failed load still enabled saving,
    // the save-on-change effects would fire on mount with DEFAULT config and
    // overwrite the user's real stored global state. A failed load must leave
    // persistence disabled so nothing is written until a remount re-reads it.
    apiGet.mockReset();
    apiGet.mockRejectedValue(new Error('network down'));

    const { unmount } = render(<InstrumentPane symbol={A} />);
    await waitFor(() => expect(chartProps).toBeTruthy());
    await waitFor(() => expect(apiGet).toHaveBeenCalledWith(expect.stringContaining(GLOBAL)));
    await act(async () => {}); // let the rejected GET settle + any effects run

    // Even a user change must not schedule a save while the load is unresolved.
    await act(async () => { chartProps.onTfChange('4H'); });

    // Unmount flushes any pending save. There must be none — nothing was written.
    await act(async () => { unmount(); });
    expect(globalSaves().length).toBe(0);
  });
});
