import { describe, expect, it } from 'vitest';
import {
  anchorMarkers, bandSeries, decisionMarkers, flowHistogram, gammaSeries, hasNavigatorIndicator,
  navigatorUnderlyingForSymbol, overlayCaveats, projectedLevels, setupMarkers, snapToBar,
} from '../navigatorOverlay';
import type {
  NavigatorChartBar, NavigatorChartResponse, NavigatorProjectedRange,
} from '../../../types/navigator';

const PALETTE = { long: '#0a0', short: '#a00', neutral: '#888', muted: '#8884', accent: '#a0f' };
const HOUR = 3600;
const T0 = 1_780_000_000;

function bar(overrides: Partial<NavigatorChartBar> = {}): NavigatorChartBar {
  return {
    t: T0, upper: 100, mid: 99, lower: 98, session_vwap: 99.5, atr: 1.2,
    relative_volume: 1.1, mid_slope: 0.2, warming_up: false, vol_score: 40,
    regime: 'EXPANSION', adx: 22, setup: null, fired: false, ...overrides,
  };
}

function range(overrides: Partial<NavigatorProjectedRange> = {}): NavigatorProjectedRange {
  return {
    available: true, period_open: 100, upper: 105, lower: 95, sample_count: 80,
    target_coverage: 0.8, conditioned: true, unavailable_reason: null, context: 'INSIDE', ...overrides,
  };
}

function response(overrides: Partial<NavigatorChartResponse> = {}): NavigatorChartResponse {
  return {
    underlying: 'NIFTY 50', token: 256265, timeframe: '60minute', enabled: true, configured: true,
    config_revision: 3, bar_count: 1, structure: [bar()], anchors: [], projected: null,
    volatility: null, flow: [], gamma: [], decisions: [], notes: [], ...overrides,
  };
}

describe('navigatorUnderlyingForSymbol', () => {
  it('keeps index and equity symbols', () => {
    expect(navigatorUnderlyingForSymbol('NSE:NIFTY BANK')).toBe('NIFTY BANK');
    expect(navigatorUnderlyingForSymbol('RELIANCE')).toBe('RELIANCE');
  });

  it('refuses option contracts so index levels never land on a premium axis', () => {
    expect(navigatorUnderlyingForSymbol('NFO:BANKNIFTY25SEP56000CE')).toBeNull();
    expect(navigatorUnderlyingForSymbol('BFO:SENSEX25SEP80000PE')).toBeNull();
  });

  it('handles empty input', () => {
    expect(navigatorUnderlyingForSymbol('')).toBeNull();
    expect(navigatorUnderlyingForSymbol(undefined)).toBeNull();
  });
});

describe('bandSeries', () => {
  it('drops warming-up bars instead of plotting them at zero', () => {
    const bars = [bar({ t: T0, mid: null }), bar({ t: T0 + HOUR, mid: 101 })];
    expect(bandSeries(bars, 'mid')).toEqual([{ time: T0 + HOUR, value: 101 }]);
  });

  it('clips to the chart window so the overlay cannot stretch the time axis', () => {
    const bars = [bar({ t: T0 - 10 * HOUR }), bar({ t: T0 }), bar({ t: T0 + 99 * HOUR })];
    const points = bandSeries(bars, 'mid', [T0, T0 + HOUR]);
    expect(points.map((p) => p.time)).toEqual([T0]);
  });
});

describe('snapToBar', () => {
  it('snaps backward to the bar whose close produced the evidence', () => {
    const times = [T0, T0 + 900, T0 + 1800];
    expect(snapToBar(times, T0 + 1000, HOUR)).toBe(T0 + 900);
  });

  it('never snaps forward — that would read as lookahead', () => {
    expect(snapToBar([T0 + 900], T0, HOUR)).toBeNull();
  });

  it('drops evidence with no bar within tolerance', () => {
    expect(snapToBar([T0], T0 + 10 * HOUR, HOUR)).toBeNull();
  });
});

describe('setupMarkers', () => {
  it('distinguishes a setup that fired from one the cooldown suppressed', () => {
    const bars = [
      bar({ t: T0, setup: 'PULLBACK_LONG', fired: true }),
      bar({ t: T0 + HOUR, setup: 'PULLBACK_LONG', fired: false }),
    ];
    const markers = setupMarkers(bars, [T0, T0 + HOUR], PALETTE);
    expect(markers[0]).toMatchObject({ shape: 'arrowUp', color: PALETTE.long, text: 'Pullback ↑' });
    expect(markers[1]).toMatchObject({ shape: 'circle', color: PALETTE.muted });
    expect(markers[1].text).toContain('cooldown');
  });

  it('points short setups the other way', () => {
    const markers = setupMarkers([bar({ setup: 'CONTINUATION_SHORT', fired: true })], [T0], PALETTE);
    expect(markers[0]).toMatchObject({ shape: 'arrowDown', position: 'aboveBar', color: PALETTE.short });
  });

  it('emits nothing for bars with no setup', () => {
    expect(setupMarkers([bar()], [T0], PALETTE)).toEqual([]);
  });
});

describe('anchorMarkers', () => {
  it('marks the confirmation bar, not the pivot bar', () => {
    const markers = anchorMarkers(
      { anchors: [{ kind: 'high', pivot_t: T0, confirmed_t: T0 + 3 * HOUR, price: 120 }] },
      [T0, T0 + 3 * HOUR], PALETTE,
    );
    expect(markers).toHaveLength(1);
    expect(markers[0].time).toBe(T0 + 3 * HOUR);
  });
});

describe('decisionMarkers', () => {
  const decision = (overrides = {}) => ({
    t: T0, decision_id: 'd1', direction: 'long', status: 'CONFIRMED', trigger: 'avwap_fresh',
    effective_score: 71.4, base_score: 85, execution_eligible: true, data_quality: 'ok',
    reason_codes: [], ...overrides,
  });

  it('shows an accepted decision as a directional arrow with its score', () => {
    const [marker] = decisionMarkers([decision()], [T0], PALETTE);
    expect(marker).toMatchObject({ shape: 'arrowUp', color: PALETTE.long });
    expect(marker.text).toBe('CONFIRMED 71 ✓');
  });

  it('shows a rejected decision as a neutral dot, not a trade arrow', () => {
    const [marker] = decisionMarkers([decision({ status: 'REJECTED', execution_eligible: false })], [T0], PALETTE);
    expect(marker).toMatchObject({ shape: 'circle', color: PALETTE.neutral });
    expect(marker.text).not.toContain('✓');
  });
});

describe('flow and gamma', () => {
  it('colours the oscillator by side and keeps the sign', () => {
    const bars = flowHistogram({
      flow: [
        { t: T0, oscillator: 0.4, state: 'CALL_DOMINANT', direction: 1, confidence: 60, quality: 'ok' },
        { t: T0 + HOUR, oscillator: -0.3, state: 'PUT_DOMINANT', direction: -1, confidence: 50, quality: 'ok' },
      ],
    }, [T0, T0 + HOUR], PALETTE);
    expect(bars.map((b) => b.color)).toEqual([PALETTE.long, PALETTE.short]);
    expect(bars.map((b) => b.value)).toEqual([0.4, -0.3]);
  });

  it('skips flow bars with no oscillator rather than drawing them flat', () => {
    const bars = flowHistogram({
      flow: [{ t: T0, oscillator: null, state: null, direction: 0, confidence: null, quality: 'unavailable' }],
    }, [T0], PALETTE);
    expect(bars).toEqual([]);
  });

  it('plots gamma as signed confidence', () => {
    const points = gammaSeries({
      gamma: [{ t: T0, signed_confidence: -30, direction: -1, confidence: 30, quality: 'ok' }],
    }, [T0]);
    expect(points).toEqual([{ time: T0, value: -30 }]);
  });
});

describe('projectedLevels', () => {
  it('draws only the ranges that actually exist', () => {
    const levels = projectedLevels({
      projected: {
        daily: range(),
        weekly: range({ available: false, upper: null, lower: null, unavailable_reason: 'only 2 completed periods, need 52' }),
      },
    });
    expect(levels.map((l) => l.label)).toEqual(['Day proj high', 'Day proj low']);
  });

  it('returns nothing when no ranges were computed', () => {
    expect(projectedLevels({ projected: null })).toEqual([]);
  });
});

describe('overlayCaveats', () => {
  it('says so when the chart timeframe cannot line up with hourly evidence', () => {
    const notes = overlayCaveats(response(), 'D');
    expect(notes[0]).toContain('hourly');
    expect(notes[0]).toContain('1H or finer');
  });

  it('notes the mismatch when hourly evidence is drawn on a finer chart', () => {
    expect(overlayCaveats(response(), '15m')[0]).toContain('15m chart');
  });

  it('stays quiet about the timeframe on a 1H chart', () => {
    expect(overlayCaveats(response(), '1H')).toEqual([]);
  });

  it('surfaces why a projected range is missing instead of hiding it', () => {
    const notes = overlayCaveats(response({
      projected: {
        daily: range({ available: false, unavailable_reason: 'only 45 completed periods, need 60' }),
        weekly: range({ available: false, unavailable_reason: 'only 9 completed periods, need 52' }),
      },
    }), '1H');
    expect(notes.some((n) => n.includes('Daily projected range unavailable'))).toBe(true);
    expect(notes.some((n) => n.includes('Weekly projected range unavailable'))).toBe(true);
  });

  it('passes the backend notes through verbatim', () => {
    const notes = overlayCaveats(response({ notes: ['Navigator is off — nothing was recorded.'] }), '1H');
    expect(notes).toContain('Navigator is off — nothing was recorded.');
  });

  it('has nothing to say without a response', () => {
    expect(overlayCaveats(null, '1H')).toEqual([]);
  });
});

describe('hasNavigatorIndicator', () => {
  it('is true only for Navigator keys', () => {
    expect(hasNavigatorIndicator(new Set(['st-fast', 'rsi']))).toBe(false);
    expect(hasNavigatorIndicator(new Set(['rsi', 'nav-flow']))).toBe(true);
  });
});
