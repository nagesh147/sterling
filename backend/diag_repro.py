"""Offline reproduction of the chart scenario — no live Kite needed.

Build a premium series like the SENSEX 76000 CE chart (low -> breakout -> decline)
and run the REAL engine + scanner grouping to see exactly what gets emitted.
"""
import asyncio
import numpy as np
from datetime import datetime, timezone, timedelta

from app.domain.models import Candle
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.services.kite_engine.scanner import (
    evaluate_derivative_contract, scanner, KiteEngineScanner,
)
from app.services.kite_engine.strikes import OptionPick
from app.services.kite_engine.universe import UniverseItem

_IST = timezone(timedelta(hours=5, minutes=30))
_TF = 3_600_000


def premium_series(n_pre=24, n_up=4, n_down=4):
    """~32 1H bars: drift-down base, explosive breakout, then decline (the chart)."""
    bars = []
    px = 120.0
    # base: drift down 120 -> 60
    for i in range(n_pre):
        px = max(50.0, px - 2.5 + np.sin(i) * 1.5)
        bars.append(px)
    # breakout up 60 -> 950
    up = np.linspace(px, 950.0, n_up + 1)[1:]
    bars.extend(up.tolist())
    # decline 950 -> 675
    dn = np.linspace(950.0, 675.0, n_down + 1)[1:]
    bars.extend(dn.tolist())
    return bars


def to_candles(closes):
    base = 1_700_000_000_000
    out = []
    prev = closes[0]
    for i, c in enumerate(closes):
        o = prev
        hi = max(o, c) * 1.01
        lo = min(o, c) * 0.99
        out.append(Candle(timestamp_ms=base + i * _TF, open=o, high=hi, low=lo, close=c, volume=1000))
        prev = c
    return out


def main():
    cfg = SterlingKiteEngineConfig()
    closes = premium_series()
    candles = to_candles(closes)
    print(f"premium bars={len(candles)}  warmup={cfg.warmup}  last_close={closes[-1]:.1f}")

    item = UniverseItem(name="SENSEX", tradingsymbol="SENSEX", token=265,
                        exchange="INDICES", option_exchange="BFO", is_index=True)
    pick = OptionPick(option_symbol="SENSEX2561876000CE", strike=76000, option_type="CE",
                      expiry="2026-06-18", dte=3, lot_size=20, token=999001)

    sigs = evaluate_derivative_contract(item, "ITM3", pick, candles, cfg)
    print(f"\n[engine] evaluate_derivative_contract -> {len(sigs)} long signals")
    latest = candles[-1].timestamp_ms
    for s in sigs:
        bar = (s.timestamp_ms - candles[0].timestamp_ms) // _TF
        fresh = s.timestamp_ms == latest
        print(f"   bar#{bar}  fresh={fresh}  ts={datetime.fromtimestamp(s.timestamp_ms/1000,_IST):%m-%d %H:%M}")
    print("   => the breakout signal IS generated" if sigs else "   => NO signal generated (engine miss)")
    print("   => is the LATEST bar fresh? ", any(s.timestamp_ms == latest for s in sigs),
          "(after-hours the breakout is NOT the latest bar => not 'ready now')")

    # --- now simulate the scanner grouping across 3 strikes of the same side ---
    print("\n[scanner grouping] 3 CE strikes (ATM/ITM1/OTM1) each firing the breakout:")
    rows = []
    for m, sym, strike, tok in (("ATM", "SENSEX...76300CE", 76300, 1),
                                 ("ITM1", "SENSEX...76200CE", 76200, 2),
                                 ("OTM1", "SENSEX...76400CE", 76400, 3)):
        pk = OptionPick(option_symbol=sym, strike=strike, option_type="CE",
                        expiry="2026-06-18", dte=3, lot_size=20, token=tok)
        rows.extend(evaluate_derivative_contract(item, m, pk, candles, cfg))
    print(f"   total drows across 3 strikes = {len(rows)} (note: multiple per strike if multiple transitions)")

    # replicate scanner.scan() grouping block
    grouped = {}
    for r in rows:
        if r.source == "derivatives":
            key = (r.underlying, r.option_type)
            if key not in grouped:
                grouped[key] = r
            else:
                grouped[key].legs.append(r.legs[0])
    for key, r in grouped.items():
        print(f"   grouped row {key}: {len(r.legs)} legs -> "
              f"{[l.option_symbol for l in r.legs]}")
    print("   => 3 distinct strikes collapse into ONE row; legs may duplicate per transition")


if __name__ == "__main__":
    main()
