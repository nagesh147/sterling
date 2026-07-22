from pathlib import Path


def replace(path, old, new):
    p = Path(path)
    text = p.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f'{path}: expected one match, got {text.count(old)}')
    p.write_text(text.replace(old, new, 1))


def write(path, content):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


replace(
    'frontend/src/types/kiteEngine.ts',
    '''  token?: number;
  is_active?: boolean; // this contract's SuperTrend still aligned on the latest bar
}

export interface EngineSignalRow {
''',
    '''  token?: number;
  is_active?: boolean; // this contract's SuperTrend still aligned on the latest bar
  signal_timestamp_ms?: number | null;
  entry_timestamp_ms?: number | null;
  alignment?: AlignmentChip | null;
  exit_state?: string | null;
}

export interface SignalChartData {
  timestamp_ms: number;
  direction: string;
  regime: string;
  source?: 'spot' | 'derivatives' | 'confluence';
  premium_signal_ms?: number | null;
  marker_basis?: 'underlying' | 'premium' | 'external';
}

export interface EngineSignalRow {
''',
)

write(
    'frontend/src/components/charts/signalMarkerLogic.ts',
    '''export type TrendDirection = 'up' | 'down';
export type TrendPoint = { direction: TrendDirection };

export function nearestCandleIndex(times: number[], targetSec: number, tolerance: number): number {
  if (!times.length || !Number.isFinite(targetSec)) return -1;
  let best = -1;
  let bestDiff = Infinity;
  for (let i = 0; i < times.length; i += 1) {
    const diff = Math.abs(times[i] - targetSec);
    if (diff < bestDiff) { best = i; bestDiff = diff; }
  }
  return bestDiff <= tolerance ? best : -1;
}

export function freshTripleAlignmentIndex(
  fast: TrendPoint[], mid: TrendPoint[], slow: TrendPoint[], times: number[],
  targetSec: number, wanted: TrendDirection, tolerance: number,
): number {
  const n = Math.min(fast.length, mid.length, slow.length, times.length);
  const all = (i: number) => fast[i]?.direction === wanted
    && mid[i]?.direction === wanted && slow[i]?.direction === wanted;
  let best = -1;
  let bestDiff = Infinity;
  for (let i = 1; i < n; i += 1) {
    if (!all(i) || all(i - 1)) continue;
    const diff = Math.abs(times[i] - targetSec);
    if (diff < bestDiff) { best = i; bestDiff = diff; }
  }
  return bestDiff <= tolerance ? best : -1;
}
''',
)

replace(
    'frontend/src/components/charts/TradingViewKiteChartLegacy.tsx',
    '''import { MiniGridPane } from './MiniGridPane';
''',
    '''import { MiniGridPane } from './MiniGridPane';
import { freshTripleAlignmentIndex, nearestCandleIndex } from './signalMarkerLogic';
import type { SignalChartData } from '../../types/kiteEngine';
''',
)
replace(
    'frontend/src/components/charts/TradingViewKiteChartLegacy.tsx',
    '''  signalData?: { timestamp_ms: number; direction: string; regime: string };
''',
    '''  signalData?: SignalChartData;
''',
)

p = Path('frontend/src/components/charts/TradingViewKiteChartLegacy.tsx')
text = p.read_text()
start = text.index('    // Signal-entry marker (native chart marker only')
end = text.index('\n    mainChartRef.current = chart;', start)
new_block = '''    // Source-aware entry marker. A PE derivative signal is still a BUY/long-
    // premium event, so the premium chart must show a fresh THREE-GREEN transition.
    // Never substitute the nearest opposite transition because the semantic regime
    // is BEAR.
    if (signalData && signalData.timestamp_ms != null && times.length && candleS) {
      try {
        const entryTargetSec = signalData.timestamp_ms / 1000;
        const premiumTargetSec = (signalData.premium_signal_ms ?? signalData.timestamp_ms) / 1000;
        const avgSpacing = times.length > 1 ? Math.abs(times[times.length - 1] - times[0]) / (times.length - 1) : Infinity;
        const tolerance = Math.max(avgSpacing * 1.25, 3600);
        const stF = supertrend(highs, lows, closes, params.stFastPeriod || 21, params.stFastMult || 1);
        const stM = supertrend(highs, lows, closes, params.stMidPeriod || 14, params.stMidMult || 2);
        const stS = supertrend(highs, lows, closes, params.stSlowPeriod || 7, params.stSlowMult || 3);
        const source = signalData.source || 'spot';
        const markers: any[] = [];

        if (source === 'derivatives' || signalData.marker_basis === 'premium') {
          const idx = freshTripleAlignmentIndex(stF, stM, stS, times, premiumTargetSec, 'up', tolerance);
          if (idx >= 0) markers.push({ time: times[idx] as any, position: 'belowBar', color: tv.green, shape: 'arrowUp', text: 'Entry' });
        } else if (source === 'confluence') {
          const confirmIdx = freshTripleAlignmentIndex(stF, stM, stS, times, premiumTargetSec, 'up', tolerance);
          if (confirmIdx >= 0) markers.push({ time: times[confirmIdx] as any, position: 'belowBar', color: tv.green, shape: 'arrowUp', text: 'Premium confirm' });
          const entryIdx = nearestCandleIndex(times, entryTargetSec, tolerance);
          if (entryIdx >= 0) markers.push({ time: times[entryIdx] as any, position: 'aboveBar', color: tv.blue, shape: 'circle', text: 'Confluence entry' });
        } else if (signalData.marker_basis === 'external') {
          const idx = nearestCandleIndex(times, entryTargetSec, tolerance);
          if (idx >= 0) markers.push({ time: times[idx] as any, position: 'aboveBar', color: tv.blue, shape: 'circle', text: 'Underlying entry' });
        } else {
          const dir = (signalData.direction || '').toLowerCase();
          const wanted = dir === 'short' || (signalData.regime || '').toUpperCase() === 'BEAR' ? 'down' : 'up';
          const idx = freshTripleAlignmentIndex(stF, stM, stS, times, entryTargetSec, wanted, tolerance);
          if (idx >= 0) markers.push({
            time: times[idx] as any,
            position: wanted === 'up' ? 'belowBar' : 'aboveBar',
            color: wanted === 'up' ? tv.green : tv.red,
            shape: wanted === 'up' ? 'arrowUp' : 'arrowDown', text: 'Entry',
          });
        }
        if (markers.length) createSeriesMarkers?.(candleS, markers);
      } catch { /* invalid metadata must never break chart rendering */ }
    }
'''
p.write_text(text[:start] + new_block + text[end:])

replace(
    'frontend/src/components/kite/InstrumentPane.tsx',
    '''import { KiteLoader } from './KiteLoader';
''',
    '''import { KiteLoader } from './KiteLoader';
import type { SignalChartData } from '../../types/kiteEngine';
''',
)
replace(
    'frontend/src/components/kite/InstrumentPane.tsx',
    '''  signalData?: { timestamp_ms: number; direction: string; regime: string };
''',
    '''  signalData?: SignalChartData;
''',
)
replace(
    'frontend/src/components/kite/InstrumentPane.tsx',
    '''function ChartView({ symbol, onSymbolChange, trailTarget, signalData }: { symbol: string; onSymbolChange?: (symbol: string) => void; trailTarget?: 'fast' | 'mid' | 'slow'; signalData?: { timestamp_ms: number; direction: string; regime: string } }) {
''',
    '''function ChartView({ symbol, onSymbolChange, trailTarget, signalData }: { symbol: string; onSymbolChange?: (symbol: string) => void; trailTarget?: 'fast' | 'mid' | 'slow'; signalData?: SignalChartData }) {
''',
)

replace(
    'frontend/src/components/kite/KiteTab.tsx',
    '''import { k } from '../../styles/kiteUI';
''',
    '''import { k } from '../../styles/kiteUI';
import type { SignalChartData } from '../../types/kiteEngine';
''',
)
replace(
    'frontend/src/components/kite/KiteTab.tsx',
    '''  const [instrumentView, setInstrumentView] = useState<{ symbol: string; tab: InstrumentTab; trailTarget?: 'fast' | 'mid' | 'slow'; signalData?: { timestamp_ms: number; direction: string; regime: string } } | null>(null);
''',
    '''  const [instrumentView, setInstrumentView] = useState<{ symbol: string; tab: InstrumentTab; trailTarget?: 'fast' | 'mid' | 'slow'; signalData?: SignalChartData } | null>(null);
''',
)
replace(
    'frontend/src/components/kite/KiteTab.tsx',
    '''  const handleOpenInstrument = (symbol: string, defaultTab: InstrumentTab | 'chart' | 'option-chain', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: { timestamp_ms: number; direction: string; regime: string }) => {
''',
    '''  const handleOpenInstrument = (symbol: string, defaultTab: InstrumentTab | 'chart' | 'option-chain', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: SignalChartData) => {
''',
)

replace(
    'frontend/src/components/kite/SterlingKiteEnginePane.tsx',
    '''  ExitMode,
} from '../../types/kiteEngine';
''',
    '''  ExitMode, SignalChartData,
} from '../../types/kiteEngine';
''',
)
replace(
    'frontend/src/components/kite/SterlingKiteEnginePane.tsx',
    '''  onOpenChart?: (symbol: string, tab: 'chart', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: { timestamp_ms: number; direction: string; regime: string }) => void;
''',
    '''  onOpenChart?: (symbol: string, tab: 'chart', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: SignalChartData) => void;
''',
)
replace(
    'frontend/src/components/kite/SterlingKiteEnginePane.tsx',
    '''  onOpenChart?: (underlying: string, tab: 'chart', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: { timestamp_ms: number; direction: string; regime: string }) => void;
''',
    '''  onOpenChart?: (underlying: string, tab: 'chart', trailTarget?: 'fast' | 'mid' | 'slow', signalData?: SignalChartData) => void;
''',
)
replace(
    'frontend/src/components/kite/SterlingKiteEnginePane.tsx',
    '''          const exitReds = row.exit_state ? (parseInt(row.exit_state, 10) || 0) : 0;
          const exitThr = row.exit_state ? (parseInt(row.exit_state.split('/')[1] || '1', 10) || 1) : 1;
          const exitColor = !row.exit_state ? k.dim : exitReds <= 0 ? k.dim : exitReds >= exitThr ? k.red : k.orange;
''',
    '''          const legExitState = leg.exit_state ?? row.exit_state;
          const exitReds = legExitState ? (parseInt(legExitState, 10) || 0) : 0;
          const exitThr = legExitState ? (parseInt(legExitState.split('/')[1] || '1', 10) || 1) : 1;
          const exitColor = !legExitState ? k.dim : exitReds <= 0 ? k.dim : exitReds >= exitThr ? k.red : k.orange;
''',
)
replace(
    'frontend/src/components/kite/SterlingKiteEnginePane.tsx',
    '''                                {row.exit_state ?? '—'}
''',
    '''                                {legExitState ?? '—'}
''',
)
replace(
    'frontend/src/components/kite/SterlingKiteEnginePane.tsx',
    '''                      onChart={(e) => { e.stopPropagation(); onOpenChart?.(`${row.exchange}:${leg.option_symbol}`, 'chart', undefined, { timestamp_ms: row.timestamp_ms, direction: row.direction, regime: row.regime }); }}
''',
    '''                      onChart={(e) => {
                        e.stopPropagation();
                        const source = row.source ?? 'spot';
                        onOpenChart?.(`${row.exchange}:${leg.option_symbol}`, 'chart', undefined, {
                          timestamp_ms: Number(leg.entry_timestamp_ms || row.timestamp_ms),
                          premium_signal_ms: leg.signal_timestamp_ms ?? null,
                          direction: row.direction, regime: row.regime, source,
                          marker_basis: source === 'spot' ? 'external' : 'premium',
                        });
                      }}
''',
)

print('frontend signal-integrity patch applied')
