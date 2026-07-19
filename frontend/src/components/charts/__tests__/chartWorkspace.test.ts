import { describe, expect, it } from 'vitest';
import {
  compileFormula,
  comparisonSeriesData,
  createChartTemplate,
  createComparisonOverlay,
  createExtraIndicator,
  exportTemplatesToJson,
  formulaSeries,
  loadTemplates,
  loadWorkspace,
  mergeImportedTemplates,
  nearestCandleIndex,
  normalizeWorkspace,
  replayDelayMs,
  saveTemplates,
  saveWorkspace,
  stepReplayIndex,
  stochastic,
  upsertTemplate,
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
      styles: { ema: { color: 'not-a-color', lineWidth: 99, visible: false } },
      extraIndicators: [
        { ...createExtraIndicator('sma', 1), period: -20 },
        { ...createExtraIndicator('ema', 1), id: 'sma-1', period: 900 },
      ],
      comparisons: [
        { id: 'c1', symbol: 'nse:infy', color: '#123456', mode: 'price', visible: false },
        { id: 'c2', symbol: 'nse:infy', color: 'bad', mode: 'bad', visible: true },
      ],
      compareSymbol: ' nse:tcs ',
      appearance: { candleUp: '#abc', candleDown: 'red', gridVisible: true },
    });
    expect(state.styles.ema.lineWidth).toBe(2);
    expect(state.styles.ema.color).toBe('#2962ff');
    expect(state.extraIndicators[0].period).toBe(1);
    expect(state.extraIndicators[1].id).toBe('sma-1-2');
    expect(state.extraIndicators[1].period).toBe(500);
    expect(state.compareSymbol).toBe('NSE:TCS');
    expect(state.comparisons.map((item) => item.symbol)).toEqual(['NSE:TCS', 'NSE:INFY']);
    expect(state.comparisons[1].mode).toBe('price');
    expect(state.comparisons[1].visible).toBe(false);
    expect(state.appearance.candleUp).toBe('#abc');
    expect(state.appearance.candleDown).toBe('#e05260');
    expect(state.appearance.gridVisible).toBe(true);
    saveWorkspace(state, storage);
    expect(loadWorkspace(storage)).toEqual(state);
  });

  it('saves, upserts, exports, and imports named templates', () => {
    const storage = memoryStorage();
    const snapshot = {
      tf: '15m',
      chartType: 'candles' as const,
      layoutMode: '1' as const,
      isHA: false,
      isLogScale: false,
      showVP: true,
      activeIndicators: ['ema', 'ema'],
      params: { ema1: 9 },
      workspace: normalizeWorkspace({ compareSymbol: 'NSE:TCS' }),
    };
    const first = createChartTemplate('Momentum', snapshot, 10);
    const replacement = createChartTemplate('Momentum', { ...snapshot, tf: '5m' }, 11);
    const upserted = upsertTemplate([first], replacement);
    expect(upserted).toHaveLength(1);
    expect(upserted[0].snapshot.tf).toBe('5m');
    saveTemplates(upserted, storage);
    expect(loadTemplates(storage)[0].snapshot.activeIndicators).toEqual(['ema']);

    const exported = exportTemplatesToJson(upserted, 12);
    expect(mergeImportedTemplates(exported, [first])[0].snapshot.tf).toBe('5m');
  });

  it('evaluates custom formulas without exposing object access or arbitrary calls', () => {
    expect(compileFormula('sqrt(close) + abs(change)')({ close: 16, change: -2 })).toBe(6);
    expect(compileFormula('close > open ? max(close, high) : min(open, low)')({ open: 10, high: 13, low: 9, close: 12 })).toBe(13);
    expect(() => compileFormula('constructor.constructor("return 1")()')({})).toThrow();
    expect(() => compileFormula('close.toString()')({ close: 1 })).toThrow();
    expect(formulaSeries('hlc3', [{ open: 1, high: 4, low: 1, close: 4, volume: 3 }])).toEqual([3]);
  });

  it('computes stochastic warmup and locates the nearest replay bar', () => {
    expect(stochastic([2, 3, 4], [0, 1, 2], [1, 2, 3], 2)).toEqual([null, 2 / 3 * 100, 2 / 3 * 100]);
    expect(createComparisonOverlay('nse:tcs', 1, 2)).toMatchObject({ symbol: 'NSE:TCS', color: '#ab47bc', mode: 'percent' });
    expect(comparisonSeriesData([{ time: 1, close: 100 }, { time: 2, close: 110 }], 'percent')).toEqual([{ time: 1, value: 0 }, { time: 2, value: 10 }]);
    expect(comparisonSeriesData([{ time: 1, close: 100 }], 'price')).toEqual([{ time: 1, value: 100 }]);
    expect(nearestCandleIndex([{ time: 10 }, { time: 20 }, { time: 30 }], 24)).toBe(1);
    expect(nearestCandleIndex([], 24)).toBe(-1);
    expect(replayDelayMs(2)).toBe(350);
    expect(replayDelayMs(100)).toBe(700);
    expect(stepReplayIndex(4, 5, 10)).toBe(5);
    expect(stepReplayIndex(null, -1, 1)).toBeNull();
  });
});
