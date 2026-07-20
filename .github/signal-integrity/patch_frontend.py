from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{path}: expected one anchor, found {count}')
    p.write_text(text.replace(old, new, 1))


wrapper = 'frontend/src/components/charts/TradingViewKiteChart.tsx'
replace_once(wrapper,
'''import { supertrend } from '../../utils/indicators';
''',
'''import { heikinAshi, supertrend } from '../../utils/indicators';
''')
replace_once(wrapper,
'''  const candles = useMemo(() => normalizeChartCandles(props.rawCandles), [props.rawCandles]);
  const activeKey = useMemo(() => Array.from(props.activeIndicators).sort().join(','), [props.activeIndicators]);
''',
'''  const candles = useMemo(() => normalizeChartCandles(props.rawCandles), [props.rawCandles]);
  const studyCandles = useMemo(() => props.isHA ? heikinAshi(candles) : candles, [candles, props.isHA]);
  const activeKey = useMemo(() => Array.from(props.activeIndicators).sort().join(','), [props.activeIndicators]);
''')
replace_once(wrapper,
'''    if (!candles.length) return [] as Array<{ key: string; label: string; values?: any[] }>;
    const highs = candles.map((bar) => bar.high);
    const lows = candles.map((bar) => bar.low);
    const closes = candles.map((bar) => bar.close);
''',
'''    if (!studyCandles.length) return [] as Array<{ key: string; label: string; values?: any[] }>;
    const highs = studyCandles.map((bar) => bar.high);
    const lows = studyCandles.map((bar) => bar.low);
    const closes = studyCandles.map((bar) => bar.close);
''')
replace_once(wrapper,
'''  }, [candles, activeKey, props.activeIndicators, props.params]);
''',
'''  }, [studyCandles, activeKey, props.activeIndicators, props.params]);
''')

required = {
    'frontend/src/types/kiteEngine.ts': [
        'export interface SignalChartData',
        'signal_timestamp_ms?: number | null',
        'entry_timestamp_ms?: number | null',
    ],
    'frontend/src/components/charts/signalMarkerLogic.ts': [
        'export function freshTripleAlignmentIndex',
        'export function nearestTimeIndex',
    ],
    'frontend/src/components/charts/TradingViewKiteChartLegacy.tsx': [
        "source === 'derivatives'",
        "freshTripleAlignmentIndex(stF, stM, stS, times, premiumTargetSec, 'up'",
        "text: 'Underlying entry'",
    ],
    'frontend/src/components/kite/InstrumentPane.tsx': ['signalData?: SignalChartData'],
    'frontend/src/components/kite/KiteTab.tsx': ['signalData?: SignalChartData'],
    'frontend/src/components/kite/SterlingKiteEnginePane.tsx': [
        'leg.entry_timestamp_ms || row.timestamp_ms',
        'premium_signal_ms: leg.signal_timestamp_ms ?? null',
        'const legExitState = leg.exit_state ?? row.exit_state',
    ],
    wrapper: [
        'props.isHA ? heikinAshi(candles) : candles',
        'const highs = studyCandles.map',
    ],
}
missing = []
for path, needles in required.items():
    text = Path(path).read_text()
    for needle in needles:
        if needle not in text:
            missing.append(f'{path}: {needle}')
if missing:
    raise RuntimeError('frontend signal-integrity source incomplete:\n' + '\n'.join(missing))
print('frontend signal-integrity source verified')
