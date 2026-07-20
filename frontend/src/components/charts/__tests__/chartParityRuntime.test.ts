import { describe, expect, it } from 'vitest';
import {
  chartRangeStart,
  directionFlipMarkers,
  normalizeChartCandles,
  resolvedChartRange,
} from '../chartParityRuntime';

describe('chart parity runtime', () => {
  it('creates arrows only when SuperTrend direction actually flips', () => {
    const markers = directionFlipMarkers(
      [
        { direction: 'up' },
        { direction: 'up' },
        { direction: 'down' },
        { direction: 'down' },
        { direction: 'up' },
      ],
      [10, 20, 30, 40, 50],
      '#00aa00',
      '#cc0000',
    );

    expect(markers).toEqual([
      { time: 30, position: 'aboveBar', color: '#cc0000', shape: 'arrowDown' },
      { time: 50, position: 'belowBar', color: '#00aa00', shape: 'arrowUp' },
    ]);
  });

  it('does not emit a seed arrow for the initial trend', () => {
    expect(directionFlipMarkers(
      [{ direction: 'down' }, { direction: 'down' }],
      [10, 20],
    )).toEqual([]);
  });

  it('ignores invalid timestamps and incomplete direction points', () => {
    expect(directionFlipMarkers(
      [{ direction: 'up' }, {} as any, { direction: 'down' }],
      [10, Number.NaN, 30],
    )).toEqual([]);
  });

  it('skips direction changes inside the SuperTrend warm-up window', () => {
    expect(directionFlipMarkers(
      [
        { direction: 'up' },
        { direction: 'down' },
        { direction: 'up' },
        { direction: 'down' },
      ],
      [10, 20, 30, 40],
      '#00aa00',
      '#cc0000',
      3,
    )).toEqual([
      { time: 40, position: 'aboveBar', color: '#cc0000', shape: 'arrowDown' },
    ]);
  });

  it('sorts candles, drops invalid rows, and keeps the newest duplicate', () => {
    expect(normalizeChartCandles([
      { time: 20, open: 2, high: 4, low: 1, close: 3, volume: 10 },
      { time: 'bad', open: 1, high: 2, low: 0, close: 1 },
      { time: 10, open: 1, high: 3, low: 0, close: 2 },
      { time: 20, open: 2, high: 5, low: 1, close: 4, volume: 12 },
    ])).toEqual([
      { time: 10, open: 1, high: 3, low: 0, close: 2, volume: 0 },
      { time: 20, open: 2, high: 5, low: 1, close: 4, volume: 12 },
    ]);
  });

  it('computes fixed and YTD date-range starts without changing All', () => {
    const last = Math.floor(Date.UTC(2026, 6, 20, 12) / 1000);
    const candles = [{ time: last - 1000 }, { time: last }];

    expect(chartRangeStart(candles, '5D')).toBe(last - 5 * 86_400);
    expect(chartRangeStart(candles, 'YTD')).toBe(Math.floor(Date.UTC(2026, 0, 1) / 1000));
    expect(chartRangeStart(candles, 'ALL')).toBeNull();
  });

  it('falls back to fit-content when the requested range predates loaded candles', () => {
    const last = 2_000_000;
    const candles = [{ time: last - 3_600 }, { time: last }];
    expect(resolvedChartRange(candles, '5D')).toBeNull();
  });

  it('returns a visible range when loaded candles cover the request', () => {
    const last = 2_000_000;
    const candles = [{ time: last - 10 * 86_400 }, { time: last }];
    expect(resolvedChartRange(candles, '5D')).toEqual({
      from: last - 5 * 86_400,
      to: last,
    });
  });
});
