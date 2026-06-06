"""Live edge signal generator.

Walks the registry's admitted combos, pulls recent bars at each combo's
timeframe, runs the shared strategy logic, and emits a `SignalContext` only
when the *latest closed bar* fires — the same entry semantics the backtest
used (signal at bar i → enter at close[i]). SL/TP come from the combo's
profile ATR multiples; conviction comes from the combo's backtest metrics.

The signals it returns are fed, unchanged, into the same `decide_both()`
selector the existing feed uses — so futures/options instrument picking is
identical; only the *source* of the signal differs.
"""
from __future__ import annotations

from typing import Callable, Sequence

import pandas as pd

from app.engines.derivatives.schemas import SignalContext
from app.engines.edge import strategies as S
from app.engines.edge.registry import PROFILE_CONFIG, EdgeRegistry

# Minimum bars to evaluate: EMA(21) + Donchian(20) + ATR(14) all need warmup.
_MIN_BARS = 40
_DEFAULT_LOOKBACK_BARS = 320

# Timeframe → minutes, for expected-hold estimation.
_TF_MINUTES = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240}
# Median winners exit well before the 200-bar time-stop; ~12 bars is a
# defensible expected hold for DTE / theta budgeting.
_EXPECTED_HOLD_BARS = 12

# Candle fetcher: (symbol, tf, lookback_bars) -> sequence of Candle-like objects
# (each with .open/.high/.low/.close/.timestamp_ms). Injected for testability.
FetchCandles = Callable[[str, str, int], Sequence]


def generate_edge_signals(
    registry: EdgeRegistry,
    *,
    fetch_candles: FetchCandles,
    lookback_bars: int = _DEFAULT_LOOKBACK_BARS,
) -> list[tuple[str, SignalContext]]:
    out: list[tuple[str, SignalContext]] = []

    for combo in registry.all():
        atr_cfg = PROFILE_CONFIG.get(combo.profile)
        signal_fn = S.SIGNAL_FNS.get(combo.strategy)
        if atr_cfg is None or signal_fn is None:
            continue

        try:
            candles = fetch_candles(combo.symbol, combo.tf, lookback_bars)
        except Exception:
            continue
        if candles is None or len(candles) < _MIN_BARS:
            continue

        df = pd.DataFrame({
            "open": [c.open for c in candles],
            "high": [c.high for c in candles],
            "low": [c.low for c in candles],
            "close": [c.close for c in candles],
        })

        sigs = signal_fn(df)
        if not bool(sigs[-1]):
            continue

        atr_val = float(S.atr14(df).iloc[-1])
        if not (atr_val > 0.0) or atr_val != atr_val:  # NaN-safe
            continue

        entry = float(df["close"].iloc[-1])
        sl = entry - atr_cfg["sl_mult"] * atr_val
        tp = entry + atr_cfg["tp_mult"] * atr_val
        rr_target = atr_cfg["tp_mult"] / atr_cfg["sl_mult"]

        last_ts = int(getattr(candles[-1], "timestamp_ms", 0))
        signal_id = (f"edge:{combo.symbol}:{combo.tf}:{combo.strategy}:"
                     f"{combo.profile}:{last_ts}")
        hold_min = _TF_MINUTES.get(combo.tf, 240) * _EXPECTED_HOLD_BARS
        # The derivatives instrument registry is keyed by the BASE underlying
        # ("BTC"), not the quote-suffixed store symbol ("BTCUSD"). Pass the base
        # so _market_context can resolve the instrument; the store fetch above
        # still used the full combo.symbol.
        underlying = combo.symbol[:-3] if combo.symbol.endswith("USD") else combo.symbol

        out.append((signal_id, SignalContext(
            strategy=f"edge/{combo.strategy}",
            underlying=underlying,
            direction="long",                 # shared strategies are long-only
            entry=entry,
            stop_loss=sl,
            take_profit=tp,
            atr=atr_val,
            rr_target=rr_target,
            signal_score=combo.signal_score,
            signal_strength="STRONG" if combo.signal_score >= 80.0 else "SIGNAL",
            expected_hold_minutes=hold_min,
            mode_name="swing",
            presized=True,        # backtest-validated SL/TP — selector won't re-cushion
        )))

    return out
