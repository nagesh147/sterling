import { describe, it, expect } from 'vitest';
import { supertrendRuns } from './indicators';

/**
 * Regression lock for the "two lines per SuperTrend indicator" bug.
 *
 * Two earlier approaches both drew TWO crossing full-width lines per indicator:
 *   1. own-direction-only arrays (bull = up-bars, bear = down-bars) — each series
 *      connected its points straight across the other trend's region.
 *   2. full-length arrays with WHITESPACE on inactive bars — this used to break the
 *      line, but lightweight-charts v5 LineSeries connects straight across whitespace
 *      too, so the green line again ran through the down-trends (verified vs 5.2.0).
 *
 * supertrendRuns fixes it by splitting into contiguous same-direction RUNS, each
 * rendered as its own short LineSeries so it spans only its own trend and can never
 * cross. Adjacent runs share a boundary vertex (each run is seeded with the prior
 * bar) so the colour flips continuously with no gap.
 */
describe('supertrendRuns', () => {
  const st = [
    { value: 10, direction: 'up' },
    { value: 11, direction: 'up' },
    { value: 20, direction: 'down' },
    { value: 21, direction: 'down' },
    { value: 12, direction: 'up' },
  ] as const;
  const times = [1, 2, 3, 4, 5];

  it('splits into contiguous single-direction runs', () => {
    const runs = supertrendRuns(st as any, times);
    expect(runs.map((r) => r.up)).toEqual([true, false, true]);
  });

  it('every run is a set of TIME-ADJACENT bars (never jumps across the other trend)', () => {
    // THE bug guard: the old approaches produced a green run holding bars [t1,t2,t5],
    // where t2->t5 skips the down region — a straight line across it. Here every
    // consecutive pair inside a run must be neighbouring bars in the time axis.
    const runs = supertrendRuns(st as any, times);
    const idx = (t: number) => times.indexOf(t);
    for (const run of runs) {
      for (let i = 1; i < run.points.length; i++) {
        expect(idx(run.points[i].time) - idx(run.points[i - 1].time)).toBe(1);
      }
    }
  });

  it('adjacent runs share a boundary vertex so the colour flips continuously', () => {
    const runs = supertrendRuns(st as any, times);
    for (let k = 1; k < runs.length; k++) {
      const prev = runs[k - 1].points;
      expect(runs[k].points[0]).toEqual(prev[prev.length - 1]);
    }
  });

  it('covers every bar exactly once as a non-seed point, in order', () => {
    const runs = supertrendRuns(st as any, times);
    // Non-seed points = run 0 in full, plus every later run minus its seed vertex.
    const covered = runs.flatMap((r, k) => (k === 0 ? r.points : r.points.slice(1)));
    expect(covered.map((p) => p.time)).toEqual(times);
    expect(covered.map((p) => p.value)).toEqual(st.map((s) => s.value));
  });

  it('handles a single-direction series as one run (no seed, no split)', () => {
    const allUp = [
      { value: 1, direction: 'up' }, { value: 2, direction: 'up' }, { value: 3, direction: 'up' },
    ] as const;
    const runs = supertrendRuns(allUp as any, [1, 2, 3]);
    expect(runs).toHaveLength(1);
    expect(runs[0].up).toBe(true);
    expect(runs[0].points).toEqual([{ time: 1, value: 1 }, { time: 2, value: 2 }, { time: 3, value: 3 }]);
  });
});
