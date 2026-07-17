import { describe, it, expect } from 'vitest';
import { supertrendSegments } from './indicators';

/**
 * Regression lock for the "two lines per SuperTrend" bug.
 *
 * The chart components used to split a SuperTrend into a `bullPts` array (only
 * up-bars) and a `bearPts` array (only down-bars) and hand each to its own
 * LineSeries. lightweight-charts connects consecutive points in a series with a
 * straight line REGARDLESS of the time gap, so the green series joined all
 * up-bars ACROSS the down regions and the red series joined all down-bars across
 * the up regions -> two full-width lines crossing the whole chart per indicator.
 *
 * supertrendSegments fixes this by returning FULL-LENGTH arrays where the
 * inactive-trend bars are whitespace points ({ time } with no `value`), which
 * makes lightweight-charts BREAK the line instead of drawing across the gap.
 */
describe('supertrendSegments', () => {
  const st = [
    { value: 10, direction: 'up' },
    { value: 11, direction: 'up' },
    { value: 20, direction: 'down' },
    { value: 21, direction: 'down' },
    { value: 12, direction: 'up' },
  ] as const;
  const times = [1, 2, 3, 4, 5];

  it('returns full-length arrays (one entry per bar) for both trends', () => {
    const { bull, bear } = supertrendSegments(st as any, times);
    expect(bull.length).toBe(st.length);
    expect(bear.length).toBe(st.length);
  });

  it('puts the value on the active trend and whitespace on the other', () => {
    const { bull, bear } = supertrendSegments(st as any, times);
    // up-bars -> bull carries value, bear is whitespace
    expect(bull[0]).toEqual({ time: 1, value: 10 });
    expect(bull[1]).toEqual({ time: 2, value: 11 });
    expect('value' in bear[0]).toBe(false);
    expect('value' in bear[1]).toBe(false);
    // down-bars -> bear carries value, bull is whitespace
    expect(bear[2]).toEqual({ time: 3, value: 20 });
    expect(bear[3]).toEqual({ time: 4, value: 21 });
    expect('value' in bull[2]).toBe(false);
    expect('value' in bull[3]).toBe(false);
    // last bar up again
    expect(bull[4]).toEqual({ time: 5, value: 12 });
    expect('value' in bear[4]).toBe(false);
  });

  it('breaks the line at every trend gap (the actual bug guard)', () => {
    const { bull, bear } = supertrendSegments(st as any, times);
    // Every bar is represented in both arrays, and each bar is a real point in
    // exactly ONE of the two arrays. That is what forces the break: a down bar
    // is whitespace in `bull`, so the green line cannot connect across it.
    for (let i = 0; i < st.length; i++) {
      const inBull = 'value' in bull[i];
      const inBear = 'value' in bear[i];
      expect(inBull).toBe(st[i].direction === 'up');
      expect(inBear).toBe(st[i].direction === 'down');
      expect(inBull).not.toBe(inBear); // never both, never neither
    }
  });

  it('carries the provided time onto every point, including whitespace', () => {
    const { bull, bear } = supertrendSegments(st as any, times);
    for (let i = 0; i < st.length; i++) {
      expect(bull[i].time).toBe(times[i]);
      expect(bear[i].time).toBe(times[i]);
    }
  });
});
