"""STRATEGY STUB — vectorized regime/signal replay removed in the strategy reset.

This module previously reimplemented the regime + signal scoring in vectorized
(O(N)) form for fast multi-timeframe backtests — the last piece of strategy
logic living under backtest/. It was stripped for the clean-slate reset
(preserved in git history on the `strategy-v2` branch).

`vectorize_replay` now returns neutral regimes/signals so the MTF backtest still
runs end-to-end but produces no trades. The `VectorizedReplay` container and the
ATR arrays are kept so `backtest_mtf` consumes the result without changes.

Reimplement the vectorized strategy here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.schemas.market import Candle
from app.schemas.directional import RegimeResult, SignalResult, MacroRegime


@dataclass
class VectorizedReplay:
    n_signal: int
    n_regime: int
    regimes_per_regime_bar: List[RegimeResult]
    signals: List[SignalResult]
    regime_idx_at_signal: np.ndarray
    signal_atr14: np.ndarray
    signal_atr22: np.ndarray
    regime_atr14: np.ndarray
    mr_signals: Optional[List[SignalResult]] = None


def _neutral_regime(close: float) -> RegimeResult:
    return RegimeResult(
        macro_regime=MacroRegime.IDLE, ema50=close, close_4h=close, score=0.0
    )


def _neutral_signal(close: float) -> SignalResult:
    return SignalResult(
        trend=0,
        all_green=False,
        all_red=False,
        green_arrow=False,
        red_arrow=False,
        st_trends=[0, 0, 0],
        st_values=[0.0, 0.0, 0.0],
        close_1h=close,
        score_long=0.0,
        score_short=0.0,
        signal_strength="NONE",
        signal_score=0.0,
    )


def vectorize_replay(
    candles_signal: List[Candle],
    candles_regime: List[Candle],
    *,
    signal_bar_ms: int,
    regime_bar_ms: int,
    st_configs: Optional[List[Tuple[int, float]]] = None,
    idle_strictness: str = "auto",
    build_mr: bool = False,
    mr_config: Optional[Dict[str, Any]] = None,
) -> VectorizedReplay:
    """Neutral replay: IDLE regimes + no-trade signals (no strategy loaded)."""
    n_signal = len(candles_signal)
    n_regime = len(candles_regime)
    regimes = [_neutral_regime(float(c.close)) for c in candles_regime]
    signals = [_neutral_signal(float(c.close)) for c in candles_signal]
    # Map every signal bar to regime index 0 so the replay loop's
    # `regime_idx < min_regime_bars` gate skips all bars -> zero trades.
    regime_idx_at_signal = np.zeros(n_signal, dtype=np.int64)
    mr_signals = (
        [_neutral_signal(float(c.close)) for c in candles_signal]
        if build_mr
        else None
    )
    return VectorizedReplay(
        n_signal=n_signal,
        n_regime=n_regime,
        regimes_per_regime_bar=regimes,
        signals=signals,
        regime_idx_at_signal=regime_idx_at_signal,
        signal_atr14=np.zeros(n_signal, dtype=np.float64),
        signal_atr22=np.zeros(n_signal, dtype=np.float64),
        regime_atr14=np.zeros(n_regime, dtype=np.float64),
        mr_signals=mr_signals,
    )
