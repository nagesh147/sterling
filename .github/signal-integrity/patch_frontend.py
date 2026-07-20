from pathlib import Path
import subprocess

path = Path('frontend/src/components/charts/TradingViewKiteChart.tsx')
text = path.read_text()
replacements = [
    ("import { supertrend } from '../../utils/indicators';\n",
     "import { heikinAshi, supertrend } from '../../utils/indicators';\n"),
    ("  const candles = useMemo(() => normalizeChartCandles(props.rawCandles), [props.rawCandles]);\n  const activeKey = useMemo(() => Array.from(props.activeIndicators).sort().join(','), [props.activeIndicators]);\n",
     "  const candles = useMemo(() => normalizeChartCandles(props.rawCandles), [props.rawCandles]);\n  const studyCandles = useMemo(() => props.isHA ? heikinAshi(candles) : candles, [candles, props.isHA]);\n  const activeKey = useMemo(() => Array.from(props.activeIndicators).sort().join(','), [props.activeIndicators]);\n"),
    ("    if (!candles.length) return [] as Array<{ key: string; label: string; values?: any[] }>;\n    const highs = candles.map((bar) => bar.high);\n    const lows = candles.map((bar) => bar.low);\n    const closes = candles.map((bar) => bar.close);\n",
     "    if (!studyCandles.length) return [] as Array<{ key: string; label: string; values?: any[] }>;\n    const highs = studyCandles.map((bar) => bar.high);\n    const lows = studyCandles.map((bar) => bar.low);\n    const closes = studyCandles.map((bar) => bar.close);\n"),
    ("  }, [candles, activeKey, props.activeIndicators, props.params]);\n",
     "  }, [studyCandles, activeKey, props.activeIndicators, props.params]);\n"),
]
for old, new in replacements:
    if new not in text and old in text:
        text = text.replace(old, new, 1)
path.write_text(text)

subprocess.run(['git', 'config', 'user.name', 'OpenAI'])
subprocess.run(['git', 'config', 'user.email', 'noreply@openai.com'])
subprocess.run(['git', 'add', str(path)])
if subprocess.run(['git', 'diff', '--cached', '--quiet']).returncode != 0:
    subprocess.run(['git', 'commit', '-m', 'fix(kite): align Heikin Ashi legend studies'])
    subprocess.run(['git', 'push', 'origin', 'HEAD:fix/kite-signal-integrity-audit'])
print('frontend HA study parity prepared and persisted')
