"""Live edge signal generator.

For each registry-admitted combo, pull recent bars at the combo's timeframe,
run the SAME strategy logic the backtest validated, and emit a SignalContext
ONLY when the latest closed bar fires. SL/TP come from the combo's profile
ATR multiples; the score comes from the combo's backtest metrics.
"""
from __future__ import annotations

from app.engines.edge.registry import EdgeCombo, EdgeRegistry, signal_score_from_metrics
from app.engines.edge.signals import generate_edge_signals
from app.schemas.market import Candle


def _candle(ts_ms, o, h, l, c, v=1000.0):
    return Candle(timestamp_ms=ts_ms, open=o, high=h, low=l, close=c, volume=v)


def _breakout_series(fire: bool):
    """45 bars (clears the 40-bar warmup floor): small oscillation, then a
    final breakout bar (or not)."""
    bars = []
    for i in range(44):
        base = 100.0 + (0.5 if i % 2 else -0.5)
        bars.append(_candle(i * 4 * 3600_000, base, base + 1.0, base - 1.0, base))
    last_close = 115.0 if fire else 100.0
    last_high = 116.0 if fire else 101.0
    bars.append(_candle(44 * 4 * 3600_000, 100.0, last_high, 99.0, last_close))
    return bars


def _registry(strategy="breakout", profile="Intraday", symbol="BTCUSD", tf="4h"):
    combo = EdgeCombo(
        symbol=symbol, tf=tf, strategy=strategy, profile=profile,
        trades=100, win_rate=0.42, pf=1.20, sharpe=1.31, expectancy=0.0032,
        net_return=0.277, pnl_usd=138.0, max_dd=-0.28,
        signal_score=signal_score_from_metrics(sharpe=1.31, expectancy=0.0032, pf=1.20),
    )
    return EdgeRegistry(combos={combo.key: combo})


def _fetcher(candles):
    def fetch(symbol, tf, lookback_bars):
        return candles
    return fetch


def test_emits_signal_when_last_bar_fires():
    reg = _registry()
    out = generate_edge_signals(reg, fetch_candles=_fetcher(_breakout_series(fire=True)))
    assert len(out) == 1
    sig_id, sig = out[0]
    assert sig.strategy == "edge/breakout"
    # underlying is the BASE symbol the derivatives instrument registry is
    # keyed by ("BTC"), NOT the CSV/store symbol "BTCUSD" — otherwise
    # _market_context's get_instrument() returns None and the row is dropped.
    assert sig.underlying == "BTC"
    assert sig.direction == "long"
    assert sig.entry == 115.0
    assert sig.signal_score > 0.0
    # signal_id keeps the full store symbol for uniqueness/traceability
    assert sig_id.startswith("edge:BTCUSD:4h:breakout:Intraday:")


def test_no_signal_when_last_bar_quiet():
    reg = _registry()
    out = generate_edge_signals(reg, fetch_candles=_fetcher(_breakout_series(fire=False)))
    assert out == []


def test_sltp_from_profile_atr_multiples():
    import pandas as pd
    from app.engines.edge import strategies as S

    candles = _breakout_series(fire=True)
    reg = _registry(profile="Intraday")  # SL 2.0 / TP 3.5
    out = generate_edge_signals(reg, fetch_candles=_fetcher(candles))
    _id, sig = out[0]

    df = pd.DataFrame({
        "open": [c.open for c in candles], "high": [c.high for c in candles],
        "low": [c.low for c in candles], "close": [c.close for c in candles],
    })
    atr = float(S.atr14(df).iloc[-1])
    assert sig.atr == atr
    assert sig.stop_loss == 115.0 - 2.0 * atr
    assert sig.take_profit == 115.0 + 3.5 * atr
    assert sig.rr_target == 3.5 / 2.0


def test_skips_when_too_few_bars():
    reg = _registry()
    out = generate_edge_signals(reg, fetch_candles=_fetcher(_breakout_series(True)[:5]))
    assert out == []


def test_skips_when_atr_degenerate():
    # Perfectly flat bars → ATR 0 → no usable stop → skip (matches simulate()).
    flat = [_candle(i * 4 * 3600_000, 100, 100, 100, 100) for i in range(30)]
    reg = _registry()
    out = generate_edge_signals(reg, fetch_candles=_fetcher(flat))
    assert out == []


def test_empty_registry_emits_nothing():
    out = generate_edge_signals(EdgeRegistry(), fetch_candles=_fetcher(_breakout_series(True)))
    assert out == []
