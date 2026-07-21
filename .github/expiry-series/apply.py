from pathlib import Path


def once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f'{path}: anchor count {text.count(old)} for {old[:100]!r}')
    p.write_text(text.replace(old, new, 1))

STRIKES='backend/app/services/kite_engine/strikes.py'
SCANNER='backend/app/services/kite_engine/scanner.py'
SERVICE='backend/app/services/kite_engine/service.py'
SCHEMAS='backend/app/engines/sterling_kite_engine/schemas.py'
TYPES='frontend/src/types/kiteEngine.ts'
PANE='frontend/src/components/kite/SterlingKiteEnginePane.tsx'
TEST='backend/tests/engines/sterling_kite_engine/test_strikes.py'

# Expiry-rank aware strike resolution.
once(STRIKES,
'''def pick_strike(
    chain: Sequence[dict],
    *,
    spot: float,
    direction: str,
    moneyness: Moneyness = "ATM",
    min_dte: int = 0