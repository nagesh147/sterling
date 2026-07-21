import { describe, expect, it } from 'vitest';
import { freshTripleAlignmentIndex, nearestTimeIndex, signalChartDataForPremiumLeg } from './signalMarkerLogic';

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


  it.each([
    ['CE', 'BULL'],
    ['PE', 'BEAR'],
  ] as const)('builds contract-local %s chart metadata that always represents a long premium entry', (optionType, regime) => {
    const row: any = {
      timestamp_ms: 999_000, direction: optionType === 'PE' ? 'short' : 'long',
      regime, source: 'derivatives',
    };
    const leg: any = {
      option_type: optionType, entry_timestamp_ms: 222_000, signal_timestamp_ms: 221_000,
    };
    const data = signalChartDataForPremiumLeg(row, leg);
    expect(data.timestamp_ms).toBe(222_000);
    expect(data.premium_signal_ms).toBe(221_000);
    expect(data.direction).toBe('long');
    expect(data.marker_basis).toBe('premium');
    expect(data.source).toBe('derivatives');
  });

  it('does not match a premium transition one hour away under strict tolerance', () => {
    const times = [100, 3700];
    const fast = [p('down'), p('up')];
    const mid = [p('down'), p('up')];
    const slow = [p('down'), p('up')];
    expect(freshTripleAlignmentIndex(fast, mid, slow, times, 100, 'up', 60)).toBe(-1);
  });

});
