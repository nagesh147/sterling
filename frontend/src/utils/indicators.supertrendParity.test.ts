import { describe, it, expect } from 'vitest';
import { heikinAshi, supertrend } from './indicators';
import fixture from './__fixtures__/supertrend_parity.json';

/**
 * Locks the frontend Heikin-Ashi + SuperTrend indicators to the BACKEND engine
 * (app/engines/indicators/{heikin_ashi,supertrend}.py). The fixture is generated
 * by the engine, so if either side's algorithm drifts, this fails. Regenerate the
 * fixture with `python backend/scripts/gen_supertrend_fixture.py` ONLY after an
 * intentional, matched change to both implementations.
 *
 * Why this matters: the engine trades on the 3-SuperTrend regime; the KITE charts
 * re-derive those lines client-side. A divergent frontend indicator (the bug this
 * guards against) makes charts show entries the engine never took.
 */
const VAL_TOL = 1e-4;

const candles = (fixture.candles as { open: number; high: number; low: number; close: number }[])
  .map((c, i) => ({ time: i, ...c }));

describe('frontend indicators match the backend engine', () => {
  it('Heikin-Ashi conversion is identical', () => {
    const ha = heikinAshi(candles as any);
    expect(ha.length).toBe(fixture.ha.open.length);
    for (let i = 0; i < ha.length; i++) {
      expect(Math.abs(ha[i].open - fixture.ha.open[i])).toBeLessThan(VAL_TOL);
      expect(Math.abs(ha[i].high - fixture.ha.high[i])).toBeLessThan(VAL_TOL);
      expect(Math.abs(ha[i].low - fixture.ha.low[i])).toBeLessThan(VAL_TOL);
      expect(Math.abs(ha[i].close - fixture.ha.close[i])).toBeLessThan(VAL_TOL);
    }
  });

  const st = fixture.supertrend as Record<string, { period: number; mult: number; dir: string[]; value: number[] }>;
  const warmup = fixture.warmup as number;

  for (const name of Object.keys(st)) {
    it(`SuperTrend "${name}" (${st[name].period},${st[name].mult}) direction + line match`, () => {
      const cfg = st[name];
      const out = supertrend(fixture.ha.high, fixture.ha.low, fixture.ha.close, cfg.period, cfg.mult);
      expect(out.length).toBe(cfg.dir.length);
      let mismatches = 0;
      for (let i = warmup; i < out.length; i++) {
        if (out[i].direction !== cfg.dir[i]) mismatches++;
        // The band value is only meaningful past the seed bar (the engine leaves
        // supertrend[period] = 0; its clamping loop starts at period + 1).
        if (i > cfg.period) expect(Math.abs(out[i].value - cfg.value[i])).toBeLessThan(VAL_TOL);
      }
      expect(mismatches).toBe(0);
    });
  }

  it('the 3-line fresh-alignment ENTRY bars match the engine exactly', () => {
    const dir: Record<string, string[]> = {};
    for (const name of Object.keys(st)) {
      dir[name] = supertrend(fixture.ha.high, fixture.ha.low, fixture.ha.close, st[name].period, st[name].mult)
        .map((p) => p.direction);
    }
    // Engine's entry = fresh full bull alignment (all three "up", not aligned prior bar).
    const feBull = (i: number) => dir.fast[i] === 'up' && dir.mid[i] === 'up' && dir.slow[i] === 'up';
    const beBull = (i: number) => st.fast.dir[i] === 'up' && st.mid.dir[i] === 'up' && st.slow.dir[i] === 'up';
    const feEntries: number[] = [];
    const beEntries: number[] = [];
    for (let i = warmup + 1; i < dir.fast.length; i++) {
      if (feBull(i) && !feBull(i - 1)) feEntries.push(i);
      if (beBull(i) && !beBull(i - 1)) beEntries.push(i);
    }
    expect(beEntries.length).toBeGreaterThan(0); // fixture must actually exercise entries
    expect(feEntries).toEqual(beEntries);
  });
});
