import { describe, expect, it } from 'vitest';
import { mergeSupertrendMarkers, supertrendFlipMarkers } from '../supertrendSignals';

describe('supertrendFlipMarkers', () => {
  it('emits arrows only when direction flips', () => {
    const markers = supertrendFlipMarkers(
      [{ direction: 'up' }, { direction: 'up' }, { direction: 'down' }, { direction: 'down' }, { direction: 'up' }],
      [1, 2, 3, 4, 5],
    );

    expect(markers).toEqual([
      { time: 3, position: 'aboveBar', color: '#f23645', shape: 'arrowDown' },
      { time: 5, position: 'belowBar', color: '#089981', shape: 'arrowUp' },
    ]);
  });

  it('ignores seeded and invalid directions', () => {
    expect(supertrendFlipMarkers(
      [{ direction: null }, { direction: 'up' }, { direction: 'up' }],
      [1, 2, 3],
    )).toEqual([]);
  });

  it('uses configured colors', () => {
    expect(supertrendFlipMarkers(
      [{ direction: 'down' }, { direction: 'up' }],
      [1, 2],
      { upColor: '#00aa00', downColor: '#aa0000' },
    )[0]).toMatchObject({ color: '#00aa00', shape: 'arrowUp' });
  });
});

describe('mergeSupertrendMarkers', () => {
  it('deduplicates coincident arrows from multiple SuperTrend variants', () => {
    const marker = { time: 10, position: 'belowBar' as const, color: '#0a0', shape: 'arrowUp' as const };
    expect(mergeSupertrendMarkers([marker], [{ ...marker, color: '#0b0' }])).toEqual([{ ...marker, color: '#0b0' }]);
  });
});
