import { describe, expect, it } from 'vitest';
import { mergeTickerSeries, pushTickerHistory } from '../KiteTicker';

describe('ticker live sparkline history', () => {
  it('appends every changed live price in order', () => {
    const symbol = 'NSE:LIVE-SPARKLINE-ORDER';
    expect(pushTickerHistory(symbol, 100, 101)).toEqual([100, 101]);
    expect(pushTickerHistory(symbol, 100, 102)).toEqual([100, 101, 102]);
    expect(pushTickerHistory(symbol, 100, 103)).toEqual([100, 101, 102, 103]);
  });

  it('does not append duplicate consecutive prices', () => {
    const symbol = 'NSE:LIVE-SPARKLINE-DEDUPE';
    pushTickerHistory(symbol, 200, 201);
    const next = pushTickerHistory(symbol, 200, 201);
    expect(next).toEqual([200, 201]);
  });

  it('keeps only the latest rolling history points', () => {
    const symbol = 'NSE:LIVE-SPARKLINE-CAP';
    for (let price = 1; price <= 60; price += 1) {
      pushTickerHistory(symbol, 1, price);
    }
    const history = pushTickerHistory(symbol, 1, 60);
    expect(history).toHaveLength(48);
    expect(history[0]).toBe(13);
    expect(history[history.length - 1]).toBe(60);
  });

  it('merges candle context with the live tick tail and respects the cap', () => {
    expect(mergeTickerSeries([98, 99, 100], [100, 101, 102], 5))
      .toEqual([98, 99, 100, 101, 102]);
  });
});
