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


PANE = 'frontend/src/components/kite/SterlingKiteEnginePane.tsx'
CHART = 'frontend/src/components/charts/TradingViewKiteChartLegacy.tsx'
MARKER_TEST = 'frontend/src/components/charts/signalMarkerLogic.test.ts'
BACKEND_TEST = 'backend/tests/engines/sterling_kite_engine/test_scanner.py'

replace_once(
    PANE,
    """import type {
