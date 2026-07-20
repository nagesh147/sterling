import {
  AreaSeries,
  BarSeries,
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
} from 'lightweight-charts';
import { heikinAshi, supertrend, type Candle, type STPoint } from '../../utils/indicators';

export type ChartRangeKey = '1D' | '5D' | '1M' | '3M' | '6M' | 'YTD' | '1Y' | '5Y' | 'ALL';

export interface ChartParityContext {
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
  isMainChart: boolean;
  context: ChartParityContext | null;
  markerApi: any | null;
  queued: boolean;
}

const PATCH_FLAG = Symbol.for('sterling.chartParityPatched');
const chartStates = new WeakMap<any, RuntimeChartState>();
const liveChartStates = new Set<RuntimeChartState>();
let currentContext: ChartParityContext | null = null;
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
): SupertrendFlipMarker[] {
  const markers: SupertrendFlipMarker[] = [];
  const count = Math.min(points.length, times.length);
  for (let index = 1; index < count; index += 1) {
    if (points[index].direction === points[index - 1].direction) continue;
    const up = points[index].direction === 'up';
    markers.push({
      time: times[index],
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
    activeIndicators.has('st-fast')
      ? { period: Number(params.stFastPeriod) || 21, multiplier: Number(params.stFastMult) || 1 }
      : null,
    activeIndicators.has('st-mid')
      ? { period: Number(params.stMidPeriod) || 14, multiplier: Number(params.stMidMult) || 2 }
      : null,
    activeIndicators.has('st-slow')
      ? { period: Number(params.stSlowPeriod) || 7, multiplier: Number(params.stSlowMult) || 3 }
      : null,
  ].filter((value): value is { period: number; multiplier: number } => !!value);
}

export function buildSupertrendFlipMarkers(context: ChartParityContext): SupertrendFlipMarker[] {
  const normalized = normalizeChartCandles(context.rawCandles);
  const candles = context.isHA ? heikinAshi(normalized) : normalized;
  if (candles.length < 2) return [];

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
    for (const marker of directionFlipMarkers(points, times, green, red)) {
      // Multiple SuperTrends often flip on the same candle. One clean arrow per
      // direction matches Kite better than three perfectly overlapping glyphs.
      const key = `${marker.time}:${marker.shape}`;
      if (seen.has(key)) continue;
      seen.add(key);
      markers.push(marker);
    }
  }

  return markers.sort((left, right) => left.time - right.time);
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

function updateMarkers(state: RuntimeChartState) {
  if (!state.isMainChart || !state.mainSeries || !state.context) return;
  const markers = buildSupertrendFlipMarkers(state.context);
  try {
    if (!state.markerApi) state.markerApi = createSeriesMarkers(state.mainSeries, markers as any);
    else state.markerApi.setMarkers(markers as any);
  } catch {
    // A chart can be disposed between a data poll and this queued update.
  }
}

function scheduleMarkerUpdate(state: RuntimeChartState) {
  if (state.queued) return;
  state.queued = true;
  queueMicrotask(() => {
    state.queued = false;
    updateMarkers(state);
  });
}

export function setChartParityContext(context: ChartParityContext) {
  currentContext = context;
  for (const state of liveChartStates) {
    if (!state.isMainChart) continue;
    state.context = context;
    scheduleMarkerUpdate(state);
  }
}

export function setChartVisibleRange(range: ChartRangeKey) {
  for (const state of liveChartStates) {
    if (!state.isMainChart || !state.context) continue;
    try {
      const timeScale = state.chart.timeScale();
      if (range === 'ALL') {
        timeScale.fitContent();
        continue;
      }
      const candles = normalizeChartCandles(state.context.rawCandles);
      if (!candles.length) continue;
      const from = chartRangeStart(candles, range);
      const to = candles[candles.length - 1].time;
      if (from != null) timeScale.setVisibleRange({ from: from as any, to: to as any });
    } catch {
      // Ignore a chart that is concurrently rebuilding.
    }
  }
}

/**
 * Adds the missing SuperTrend flip markers without forcing the chart component
 * to rebuild on every candle poll. We patch the public chart API prototype once,
 * then keep a separate marker primitive updated from the wrapper's fresh props.
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
    if (typeof originalAddSeries !== 'function' || typeof originalRemove !== 'function') return;

    chartPrototype.addSeries = function patchedAddSeries(seriesDefinition: any, options: any = {}) {
      const series = originalAddSeries.call(this, seriesDefinition, options);
      let state = chartStates.get(this);
      if (!state) {
        state = {
          chart: this,
          firstSeries: null,
          mainSeries: null,
          isMainChart: false,
          context: currentContext,
          markerApi: null,
          queued: false,
        };
        chartStates.set(this, state);
        liveChartStates.add(state);
      }

      if (!state.firstSeries) state.firstSeries = series;
      if (!state.mainSeries && (
        seriesDefinition === CandlestickSeries ||
        seriesDefinition === BarSeries ||
        seriesDefinition === AreaSeries
      )) {
        state.mainSeries = series;
        state.isMainChart = true;
      }

      const title = String(options?.title || '');
      if (/^(ST\s|SuperTrend)/i.test(title)) {
        state.isMainChart = true;
        state.mainSeries ||= state.firstSeries;
      }

      try {
        const originalSetData = series.setData.bind(series);
        series.setData = (data: any[]) => {
          originalSetData(data);
          if (series === state!.mainSeries || /^(ST\s|SuperTrend)/i.test(title)) {
            state!.context = currentContext || state!.context;
            scheduleMarkerUpdate(state!);
          }
        };
      } catch {
        // The library currently exposes writable methods; retain normal behavior
        // should a future release make the series API non-writable.
      }

      if (state.isMainChart) scheduleMarkerUpdate(state);
      return series;
    };

    chartPrototype.remove = function patchedRemove(...args: any[]) {
      const state = chartStates.get(this);
      if (state) {
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
