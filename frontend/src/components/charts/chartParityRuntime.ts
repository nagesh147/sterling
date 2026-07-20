import {
  AreaSeries,
  BarSeries,
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
} from 'lightweight-charts';
import { heikinAshi, supertrend, type Candle, type STPoint } from '../../utils/indicators';

export type ChartRangeKey = '1D' | '5D' | '1M' | '3M' | '6M' | 'YTD' | '1Y' | '5Y' | 'ALL';

export const CHART_CROSSHAIR_EVENT = 'sterling-chart-crosshair';
export interface ChartCrosshairEventDetail {
  contextId: string;
  bar: null | { time: number; open: number; high: number; low: number; close: number };
}

export interface ChartParityContext {
  id: string;
  symbol: string;
  tf: string;
  rawCandles: any[];
  isHA: boolean;
  activeIndicators: Set<string>;
  params: Record<string, any>;
  theme: Record<string, any>;
}

export interface SupertrendFlipMarker {
  time: number;
  position: 'aboveBar' | 'belowBar';
  color: string;
  shape: 'arrowDown' | 'arrowUp';
}

interface RuntimeChartState {
  chart: any;
  firstSeries: any | null;
  mainSeries: any | null;
  contextId: string | null;
  markerApi: any | null;
  markerFrame: number | null;
  primary: boolean;
}

interface MarkerCacheEntry {
  signature: string;
  markers: SupertrendFlipMarker[];
}

const PATCH_FLAG = Symbol.for('sterling.chartParityPatched');
const chartStates = new WeakMap<any, RuntimeChartState>();
const liveChartStates = new Set<RuntimeChartState>();
const contexts = new Map<string, ChartParityContext>();
const primaryStates = new Map<string, RuntimeChartState>();
const markerCache = new Map<string, MarkerCacheEntry>();
let pendingContextId: string | null = null;
let installed = false;

const DAY_SECONDS = 86_400;
export const CHART_RANGE_KEYS: ChartRangeKey[] = ['1D', '5D', '1M', '3M', '6M', 'YTD', '1Y', '5Y', 'ALL'];

export function normalizeChartCandles(rawCandles: any[]): Candle[] {
  const byTime = new Map<number, Candle>();
  for (const raw of rawCandles || []) {
    const time = Number(raw?.time);
    const open = Number(raw?.open);
    const high = Number(raw?.high);
    const low = Number(raw?.low);
    const close = Number(raw?.close);
    if (![time, open, high, low, close].every(Number.isFinite)) continue;
    byTime.set(time, {
      time,
      open,
      high,
      low,
      close,
      volume: Number.isFinite(Number(raw?.volume)) ? Number(raw.volume) : 0,
    });
  }
  return Array.from(byTime.values()).sort((a, b) => a.time - b.time);
}

export function directionFlipMarkers(
  points: Pick<STPoint, 'direction'>[],
  times: number[],
  green = '#26a69a',
  red = '#ef5350',
  startIndex = 1,
): SupertrendFlipMarker[] {
  const markers: SupertrendFlipMarker[] = [];
  const count = Math.min(points.length, times.length);
  for (let index = Math.max(1, startIndex); index < count; index += 1) {
    const previous = points[index - 1]?.direction;
    const current = points[index]?.direction;
    const time = times[index];
    if (!previous || !current || previous === current || !Number.isFinite(time)) continue;
    const up = current === 'up';
    markers.push({
      time,
      position: up ? 'belowBar' : 'aboveBar',
      color: up ? green : red,
      shape: up ? 'arrowUp' : 'arrowDown',
    });
  }
  return markers;
}

function activeSupertrendConfigs(context: ChartParityContext) {
  const { activeIndicators, params } = context;
  return [
    activeIndicators.has('st-fast') ? { key: 'fast', period: Number(params.stFastPeriod) || 21, multiplier: Number(params.stFastMult) || 1 } : null,
    activeIndicators.has('st-mid') ? { key: 'mid', period: Number(params.stMidPeriod) || 14, multiplier: Number(params.stMidMult) || 2 } : null,
    activeIndicators.has('st-slow') ? { key: 'slow', period: Number(params.stSlowPeriod) || 7, multiplier: Number(params.stSlowMult) || 3 } : null,
  ].filter((value): value is { key: string; period: number; multiplier: number } => !!value);
}

function markerSignature(context: ChartParityContext) {
  const raw = context.rawCandles || [];
  const last = raw[raw.length - 1];
  const first = raw[0];
  const configs = activeSupertrendConfigs(context).map((config) => `${config.key}:${config.period}:${config.multiplier}`).join('|');
  return [
    context.symbol,
    context.tf,
    context.isHA ? 'ha' : 'raw',
    raw.length,
    first?.time ?? '',
    last?.time ?? '',
    last?.open ?? '',
    last?.high ?? '',
    last?.low ?? '',
    last?.close ?? '',
    configs,
    context.theme?.green || '',
    context.theme?.red || '',
  ].join(':');
}

export function buildSupertrendFlipMarkers(context: ChartParityContext): SupertrendFlipMarker[] {
  const signature = markerSignature(context);
  const cached = markerCache.get(context.id);
  if (cached?.signature === signature) return cached.markers;

  const normalized = normalizeChartCandles(context.rawCandles);
  const candles = context.isHA ? heikinAshi(normalized) : normalized;
  if (candles.length < 2) {
    markerCache.set(context.id, { signature, markers: [] });
    return [];
  }

  const times = candles.map((candle) => candle.time);
  const highs = candles.map((candle) => candle.high);
  const lows = candles.map((candle) => candle.low);
  const closes = candles.map((candle) => candle.close);
  const green = context.theme?.green || '#26a69a';
  const red = context.theme?.red || '#ef5350';
  const seen = new Set<string>();
  const markers: SupertrendFlipMarker[] = [];

  for (const config of activeSupertrendConfigs(context)) {
    const points = supertrend(highs, lows, closes, Math.max(1, config.period), Math.max(0.1, config.multiplier));
    for (const marker of directionFlipMarkers(points, times, green, red, config.period + 1)) {
      const key = `${marker.time}:${marker.shape}`;
      if (seen.has(key)) continue;
      seen.add(key);
      markers.push(marker);
    }
  }

  markers.sort((left, right) => left.time - right.time);
  markerCache.set(context.id, { signature, markers });
  return markers;
}

export function chartRangeStart(candles: Pick<Candle, 'time'>[], range: ChartRangeKey): number | null {
  if (!candles.length || range === 'ALL') return null;
  const lastTime = candles[candles.length - 1].time;
  if (range === 'YTD') {
    const date = new Date(lastTime * 1000);
    return Math.floor(Date.UTC(date.getUTCFullYear(), 0, 1) / 1000);
  }
  const days: Record<Exclude<ChartRangeKey, 'YTD' | 'ALL'>, number> = {
    '1D': 1,
    '5D': 5,
    '1M': 30,
    '3M': 90,
    '6M': 180,
    '1Y': 365,
    '5Y': 365 * 5,
  };
  return lastTime - days[range] * DAY_SECONDS;
}

export function resolvedChartRange(candles: Pick<Candle, 'time'>[], range: ChartRangeKey): { from: number; to: number } | null {
  if (!candles.length || range === 'ALL') return null;
  const first = candles[0].time;
  const to = candles[candles.length - 1].time;
  const requested = chartRangeStart(candles, range);
  if (requested == null || requested <= first) return null;
  return { from: requested, to };
}

function stateContext(state: RuntimeChartState) {
  return state.contextId ? contexts.get(state.contextId) || null : null;
}

function updateMarkers(state: RuntimeChartState) {
  const context = stateContext(state);
  if (!state.primary || !state.mainSeries || !context) return;
  const markers = buildSupertrendFlipMarkers(context);
  try {
    if (!state.markerApi) state.markerApi = createSeriesMarkers(state.mainSeries, markers as any, { autoScale: false });
    else state.markerApi.setMarkers(markers as any);
  } catch {
    // The chart may be disposed between a queued update and the animation frame.
  }
}

function scheduleMarkerUpdate(state: RuntimeChartState) {
  if (state.markerFrame != null) return;
  state.markerFrame = requestAnimationFrame(() => {
    state.markerFrame = null;
    updateMarkers(state);
  });
}

export function setChartParityContext(context: ChartParityContext) {
  contexts.set(context.id, context);
  pendingContextId = context.id;
  for (const state of liveChartStates) {
    if (!state.primary || state.contextId !== context.id) continue;
    scheduleMarkerUpdate(state);
  }
}

export function removeChartParityContext(contextId: string) {
  contexts.delete(contextId);
  markerCache.delete(contextId);
  if (pendingContextId === contextId) pendingContextId = null;
  for (const state of liveChartStates) {
    if (state.contextId !== contextId) continue;
    if (state.primary && primaryStates.get(contextId) === state) primaryStates.delete(contextId);
    state.contextId = null;
    if (state.markerFrame != null) cancelAnimationFrame(state.markerFrame);
    state.markerFrame = null;
    try { state.markerApi?.setMarkers([]); } catch {}
  }
}

export function setChartVisibleRange(contextId: string, range: ChartRangeKey) {
  const context = contexts.get(contextId);
  if (!context) return;
  const candles = normalizeChartCandles(context.rawCandles);
  const visibleRange = resolvedChartRange(candles, range);
  for (const state of liveChartStates) {
    if (!state.primary || state.contextId !== contextId) continue;
    try {
      const timeScale = state.chart.timeScale();
      if (!visibleRange) timeScale.fitContent();
      else timeScale.setVisibleRange({ from: visibleRange.from as any, to: visibleRange.to as any });
    } catch {
      // Ignore a chart that is concurrently rebuilding.
    }
  }
}

function barFromCrosshair(param: any, state: RuntimeChartState): ChartCrosshairEventDetail['bar'] {
  if (!param?.time || !param?.seriesPrices || !state.mainSeries) return null;
  const value = param.seriesPrices.get(state.mainSeries);
  if (!value || typeof value !== 'object') return null;
  const open = Number(value.open);
  const high = Number(value.high);
  const low = Number(value.low);
  const close = Number(value.close);
  if (![open, high, low, close].every(Number.isFinite)) return null;
  return { time: Number(param.time), open, high, low, close };
}

/**
 * Tracks the primary lightweight-charts instance and adds Zerodha parity behavior
 * without coupling the outer React shell to the large legacy workspace.
 */
export function installChartParityRuntime() {
  if (installed || typeof document === 'undefined' || import.meta.env.MODE === 'test') return;
  installed = true;

  const host = document.createElement('div');
  host.setAttribute('aria-hidden', 'true');
  Object.assign(host.style, {
    position: 'fixed',
    left: '-10000px',
    top: '-10000px',
    width: '2px',
    height: '2px',
    overflow: 'hidden',
    pointerEvents: 'none',
  });
  (document.body || document.documentElement).appendChild(host);

  let probeChart: any = null;
  try {
    probeChart = createChart(host, { width: 2, height: 2 });
    const chartPrototype: any = Object.getPrototypeOf(probeChart);
    if (!chartPrototype || chartPrototype[PATCH_FLAG]) return;

    const originalAddSeries = chartPrototype.addSeries;
    const originalRemove = chartPrototype.remove;
    const originalSubscribeCrosshairMove = chartPrototype.subscribeCrosshairMove;
    if (typeof originalAddSeries !== 'function' || typeof originalRemove !== 'function') return;

    chartPrototype.addSeries = function patchedAddSeries(seriesDefinition: any, options: any = {}) {
      const series = originalAddSeries.call(this, seriesDefinition, options);
      let state = chartStates.get(this);
      if (!state) {
        state = {
          chart: this,
          firstSeries: null,
          mainSeries: null,
          contextId: pendingContextId,
          markerApi: null,
          markerFrame: null,
          primary: false,
        };
        if (state.contextId && !primaryStates.has(state.contextId)) {
          state.primary = true;
          primaryStates.set(state.contextId, state);
        }
        chartStates.set(this, state);
        liveChartStates.add(state);
      }

      if (!state.firstSeries) state.firstSeries = series;
      if (state.primary && !state.mainSeries && (
        seriesDefinition === CandlestickSeries ||
        seriesDefinition === BarSeries ||
        seriesDefinition === AreaSeries
      )) state.mainSeries = series;

      const title = String(options?.title || '');
      if (state.primary && /^(ST\s|SuperTrend)/i.test(title)) state.mainSeries ||= state.firstSeries;

      try {
        const originalSetData = series.setData.bind(series);
        series.setData = (data: any[]) => {
          originalSetData(data);
          if (state!.primary && (series === state!.mainSeries || /^(ST\s|SuperTrend)/i.test(title))) scheduleMarkerUpdate(state!);
        };
      } catch {
        // Keep normal chart behavior if a future library release seals methods.
      }

      if (state.primary && state.mainSeries) scheduleMarkerUpdate(state);
      return series;
    };

    if (typeof originalSubscribeCrosshairMove === 'function') {
      chartPrototype.subscribeCrosshairMove = function patchedSubscribeCrosshairMove(handler: (param: any) => void) {
        let frame: number | null = null;
        let latest: any = null;
        const throttled = (param: any) => {
          latest = param;
          if (frame != null) return;
          frame = requestAnimationFrame(() => {
            frame = null;
            const value = latest;
            latest = null;
            handler(value);
            const state = chartStates.get(this);
            if (!state?.primary || !state.contextId) return;
            window.dispatchEvent(new CustomEvent<ChartCrosshairEventDetail>(CHART_CROSSHAIR_EVENT, {
              detail: { contextId: state.contextId, bar: barFromCrosshair(value, state) },
            }));
          });
        };
        return originalSubscribeCrosshairMove.call(this, throttled);
      };
    }

    chartPrototype.remove = function patchedRemove(...args: any[]) {
      const state = chartStates.get(this);
      if (state) {
        if (state.markerFrame != null) cancelAnimationFrame(state.markerFrame);
        if (state.primary && state.contextId && primaryStates.get(state.contextId) === state) primaryStates.delete(state.contextId);
        liveChartStates.delete(state);
        chartStates.delete(this);
      }
      return originalRemove.apply(this, args);
    };

    chartPrototype[PATCH_FLAG] = true;
  } catch {
    installed = false;
  } finally {
    try { probeChart?.remove(); } catch {}
    host.remove();
  }
}
