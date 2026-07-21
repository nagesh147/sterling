from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


MARKER = 'frontend/src/components/charts/signalMarkerLogic.ts'
MARKER_TEST = 'frontend/src/components/charts/signalMarkerLogic.test.ts'
PANE = 'frontend/src/components/kite/SterlingKiteEnginePane.tsx'
CHART = 'frontend/src/components/charts/TradingViewKiteChartLegacy.tsx'
BACKEND_TEST = 'backend/tests/engines/sterling_kite_engine/test_scanner.py'

replace_once(
    MARKER,
    "export type TrendDirection = 'up' | 'down';\n",
    "import type { EngineSignalRow, OptionLeg, SignalChartData } from '../../types/kiteEngine';\n\nexport type TrendDirection = 'up' | 'down';\n",
)

marker_helper = '''\n\n/** Build chart metadata from the selected option contract, never from its grouped parent.\n * CE and PE are both long-premium BUY signals, so premium markers always seek a\n * fresh three-green transition regardless of the underlying BULL/BEAR regime. */\nexport function signalChartDataForPremiumLeg(\n  row: EngineSignalRow, leg: OptionLeg,\n): SignalChartData {\n  const entryTs = leg.entry_timestamp_ms ?? leg.signal_timestamp_ms ?? row.timestamp_ms;\n  const premiumTs = leg.signal_timestamp_ms ?? leg.entry_timestamp_ms ?? row.timestamp_ms;\n  return {\n    timestamp_ms: entryTs,\n    direction: 'long',\n    regime: row.regime,\n    source: row.source === 'confluence' ? 'confluence' : 'derivatives',\n    premium_signal_ms: premiumTs,\n    marker_basis: 'premium',\n  };\n}\n'''
marker_text = Path(MARKER).read_text()
if 'export function signalChartDataForPremiumLeg' not in marker_text:
    Path(MARKER).write_text(marker_text.rstrip() + marker_helper)

replace_once(
    PANE,
    "import { useSignalMarkers, type Marker } from '../../store/useSignalMarkers';\n",
    "import { useSignalMarkers, type Marker } from '../../store/useSignalMarkers';\nimport { signalChartDataForPremiumLeg } from '../charts/signalMarkerLogic';\n",
)

replace_once(
    PANE,
    "onChart={(e) => { e.stopPropagation(); onOpenChart?.(`${row.exchange}:${leg.option_symbol}`, 'chart', undefined, { timestamp_ms: row.timestamp_ms, direction: row.direction, regime: row.regime }); }}",
    "onChart={(e) => { e.stopPropagation(); onOpenChart?.(`${row.exchange}:${leg.option_symbol}`, 'chart', undefined, signalChartDataForPremiumLeg(row, leg)); }}",
)

replace_once(
    PANE,
    "{row.exit_state ?? '—'}",
    "{legExitState ?? '—'}",
)

old_marker_block = '''        const avgSpacing = times.length > 1 ? Math.abs(times[times.length - 1] - times[0]) / (times.length - 1) : Infinity;
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
          const idx = freshTripleAlignmentIndex(stF, stM, stS, times, premiumTargetSec, 'up', tolerance);
          if (idx >= 0) markers.push({ time: times[idx] as any, position: 'belowBar', color: tv.green, shape: 'arrowUp', text: 'Confluence' });
        } else if (signalData.marker_basis === 'external') {
          const idx = nearestTimeIndex(times, entryTargetSec, tolerance);
          if (idx >= 0) markers.push({ time: times[idx] as any, position: 'aboveBar', color: tv.blue, shape: 'circle', text: 'Underlying entry' });
        } else {
          const dir = (signalData.direction || '').toLowerCase();
          const wanted = dir === 'short' || (signalData.regime || '').toUpperCase() === 'BEAR' ? 'down' : 'up';
          const idx = freshTripleAlignmentIndex(stF, stM, stS, times, entryTargetSec, wanted, tolerance);
'''
new_marker_block = '''        const avgSpacing = times.length > 1 ? Math.abs(times[times.length - 1] - times[0]) / (times.length - 1) : Infinity;
        const broadTolerance = Math.max(avgSpacing * 1.25, 3600);
        // Premium timestamps are emitted from the exact option candle. Keep this
        // strict so a grouped-parent timestamp cannot snap to a neighbouring bar.
        const premiumTolerance = 60;
        const stF = supertrend(highs, lows, closes, params.stFastPeriod || 21, params.stFastMult || 1);
        const stM = supertrend(highs, lows, closes, params.stMidPeriod || 14, params.stMidMult || 2);
        const stS = supertrend(highs, lows, closes, params.stSlowPeriod || 7, params.stSlowMult || 3);
        const source = signalData.source || 'spot';
        const markers: any[] = [];

        // Confluence is checked before the generic premium-basis branch so its label
        // remains reachable. Both CE and PE premium confirmations are three-green.
        if (source === 'confluence') {
          const idx = freshTripleAlignmentIndex(stF, stM, stS, times, premiumTargetSec, 'up', premiumTolerance);
          if (idx >= 0) markers.push({ time: times[idx] as any, position: 'belowBar', color: tv.green, shape: 'arrowUp', text: 'Confluence' });
        } else if (source === 'derivatives' || signalData.marker_basis === 'premium') {
          const idx = freshTripleAlignmentIndex(stF, stM, stS, times, premiumTargetSec, 'up', premiumTolerance);
          if (idx >= 0) markers.push({ time: times[idx] as any, position: 'belowBar', color: tv.green, shape: 'arrowUp', text: 'Entry' });
        } else if (signalData.marker_basis === 'external') {
          const idx = nearestTimeIndex(times, entryTargetSec, broadTolerance);
          if (idx >= 0) markers.push({ time: times[idx] as any, position: 'aboveBar', color: tv.blue, shape: 'circle', text: 'Underlying entry' });
        } else {
          const dir = (signalData.direction || '').toLowerCase();
          const wanted = dir === 'short' || (signalData.regime || '').toUpperCase() === 'BEAR' ? 'down' : 'up';
          const idx = freshTripleAlignmentIndex(stF, stM, stS, times, entryTargetSec, wanted, broadTolerance);
'''
replace_once(CHART, old_marker_block, new_marker_block)

frontend_tests = '''\n\n  it.each([\n    ['CE', 'BULL'],\n    ['PE', 'BEAR'],\n  ] as const)('builds contract-local %s chart metadata that always represents a long premium entry', (optionType, regime) => {\n    const row: any = {\n      timestamp_ms: 999_000, direction: optionType === 'PE' ? 'short' : 'long',\n      regime, source: 'derivatives',\n    };\n    const leg: any = {\n      option_type: optionType, entry_timestamp_ms: 222_000, signal_timestamp_ms: 221_000,\n    };\n    const data = signalChartDataForPremiumLeg(row, leg);\n    expect(data.timestamp_ms).toBe(222_000);\n    expect(data.premium_signal_ms).toBe(221_000);\n    expect(data.direction).toBe('long');\n    expect(data.marker_basis).toBe('premium');\n    expect(data.source).toBe('derivatives');\n  });\n\n  it('does not match a premium transition one hour away under strict tolerance', () => {\n    const times = [100, 3700];\n    const fast = [p('down'), p('up')];\n    const mid = [p('down'), p('up')];\n    const slow = [p('down'), p('up')];\n    expect(freshTripleAlignmentIndex(fast, mid, slow, times, 100, 'up', 60)).toBe(-1);\n  });\n'''
marker_test_text = Path(MARKER_TEST).read_text()
if 'builds contract-local %s chart metadata' not in marker_test_text:
    marker_test_text = marker_test_text.replace(
        "import { freshTripleAlignmentIndex, nearestTimeIndex } from './signalMarkerLogic';",
        "import { freshTripleAlignmentIndex, nearestTimeIndex, signalChartDataForPremiumLeg } from './signalMarkerLogic';",
    )
    marker_test_text = marker_test_text.rstrip()
    if not marker_test_text.endswith('});'):
        raise RuntimeError('unexpected marker test ending')
    marker_test_text = marker_test_text[:-3] + frontend_tests + '\n});\n'
    Path(MARKER_TEST).write_text(marker_test_text)

backend_test = '''\n\n@pytest.mark.parametrize("option_type", ["CE", "PE"])
def test_derivative_contract_never_treats_three_red_as_an_entry(option_type):
    """A premium down-transition is an exit state, never a CE/PE BUY entry."""
    cfg = SterlingKiteEngineConfig()
    item = UniverseItem("HDFCBANK", "HDFCBANK", 1, "NSE", "NFO")
    pick = OptionPick(option_symbol=f"HDFCBANK26JUL825{option_type}", strike=825.0,
                      option_type=option_type, expiry="2026-07-30", dte=9,
                      lot_size=550, token=12345)
    candles = _trim_to_transition(_candles(_fresh_short_path()), cfg, "short")
    assert evaluate_derivative_contract(item, "ITM3", pick, candles, cfg) == []
'''
backend_text = Path(BACKEND_TEST).read_text()
if 'test_derivative_contract_never_treats_three_red_as_an_entry' not in backend_text:
    Path(BACKEND_TEST).write_text(backend_text.rstrip() + backend_test + '\n')

# Fail closed on every critical invariant.
assert 'signalChartDataForPremiumLeg(row, leg)' in Path(PANE).read_text()
assert "{legExitState ?? '—'}" in Path(PANE).read_text()
chart = Path(CHART).read_text()
assert 'const premiumTolerance = 60;' in chart
assert chart.index("if (source === 'confluence')") < chart.index("source === 'derivatives'")
assert "premiumTargetSec, 'up', premiumTolerance" in chart
assert 'test_derivative_contract_never_treats_three_red_as_an_entry' in Path(BACKEND_TEST).read_text()
print('CE/PE signal integrity hardening applied')
