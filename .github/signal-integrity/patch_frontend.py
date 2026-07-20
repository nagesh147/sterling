from pathlib import Path

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
    'frontend/src/components/charts/TradingViewKiteChart.tsx': [
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
