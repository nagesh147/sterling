import { describe, expect, it } from 'vitest';
import { freshTripleAlignmentIndex, nearestTimeIndex } from './signalMarkerLogic';

const p = (direction: 'up' | 'down') => ({ direction });

describe('signal marker integrity', () => {
  it.each(['CE', 'PE'])('never substitutes a nearby three-red transition for a %s long-premium entry', () => {
    const times = [100, 200, 300, 400];
    const fast = [p('up'), p('down'), p('down'), p('up')];
    const mid = [p('up'), p('down'), p('down'), p('up')];
    const slow = [p('up'), p('down'), p('down'), p('up')];
    expect(freshTripleAlignmentIndex(fast, mid, slow, times, 200, 'up', 150)).toBe(-1);
    expect(freshTripleAlignmentIndex(fast, mid, slow, times, 200, 'down', 150)).toBe(1);
  });

  it.each(['CE', 'PE'])('finds the intended fresh three-green %s premium transition', () => {
    const times = [100, 200, 300];
    const fast = [p('down'), p('up'), p('up')];
    const mid = [p('down'), p('up'), p('up')];
    const slow = [p('down'), p('up'), p('up')];
    expect(freshTripleAlignmentIndex(fast, mid, slow, times, 205, 'up', 20)).toBe(1);
  });

  it('only returns an external time marker inside tolerance', () => {
    expect(nearestTimeIndex([100, 200, 300], 205, 10)).toBe(1);
    expect(nearestTimeIndex([100, 200, 300], 500, 10)).toBe(-1);
  });
});
