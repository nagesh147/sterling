import { describe, expect, it } from 'vitest';
import {
  compileFormula,
  createExtraIndicator,
  formulaSeries,
  loadTemplates,
  loadWorkspace,
  nearestCandleIndex,
  normalizeWorkspace,
  saveTemplates,
  saveWorkspace,
  stochastic,
} from '../chartWorkspace';

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
  };
}

describe('chart workspace', () => {
  it('normalizes corrupt persisted state and round-trips valid settings', () => {
    const storage = memoryStorage();
    const state = normalizeWorkspace({
      styles: { ema: { color: '#123456', lineWidth: 99, visible: false } },
      extraIndicators: [{ ...createExtraIndicator('sma', 1), period: -20 }],
      compareSymbol: 'NSE:TCS',
      appearance: { gridVisible: true },
    });
    expect(state.styles.ema.lineWidth).toBe(2);
    expect(state.extraIndicators[0].period).toBe(1);
    expect(state.appearance.gridVisible).toBe(true);
    saveWorkspace(state, storage);
    expect(loadWorkspace(storage)).toEqual(state);
  });

  it('saves and loads named templates', () => {
    const storage = memoryStorage();
    const template = { id: 'one', name: 'Momentum', createdAt: 10, snapshot: {} as any };
    saveTemplates([template], storage);
    expect(loadTemplates(storage)).toEqual([template]);
  });

  it('evaluates custom formulas without exposing object access or arbitrary calls', () => {
    expect(compileFormula('sqrt(close) + abs(change)')({ close: 16, change: -2 })).toBe(6);
    expect(() => compileFormula('constructor.constructor("return 1")()')({})).toThrow();
    expect(formulaSeries('hlc3', [{ open: 1, high: 4, low: 1, close: 4, volume: 3 }])).toEqual([3]);
  });

  it('computes stochastic warmup and locates the nearest replay bar', () => {
    expect(stochastic([2, 3, 4], [0, 1, 2], [1, 2, 3], 2)).toEqual([null, 2 / 3 * 100, 2 / 3 * 100]);
    expect(nearestCandleIndex([{ time: 10 }, { time: 20 }, { time: 30 }], 24)).toBe(1);
    expect(nearestCandleIndex([], 24)).toBe(-1);
  });
});
