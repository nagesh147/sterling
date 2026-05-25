"""Configuration for the daily RSI(2) mean-reversion strategy.

A small surface. The strategy buys short-term oversold pullbacks *inside* an
uptrend and exits on the snap-back — the classic Connors RSI(2) system, here
validated across a 25-coin crypto basket (PF ≈ 3.0, ~71% win rate, stable
out-of-sample; the earlier momentum rule had no edge).

Strategy rule (1D timeframe)
----------------------------
    Regime      : long only while close > SMA(trend_sma_period)
    Long entry  : RSI(rsi_period) < rsi_oversold
    Long exit   : RSI(rsi_period) > rsi_exit

    Short (mirror, opt-in, UNVALIDATED):
    Regime      : close < SMA(trend_sma_period)
    Short entry : RSI > (100 - rsi_oversold)
    Short exit  : RSI < (100 - rsi_exit)

A wide ATR stop is a risk-defining safety net and the position-sizing anchor;
the primary exit is the RSI snap-back. Defaults match the validated config.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TripleSTConfig(BaseModel):
    """Operator-facing config bundle. Echoed in every evaluation/backtest
    response so the UI always renders against the exact parameters used.
    """

    # Primary timeframe — the rule is defined on daily candles.
    timeframe: str = "1d"

    # ── Trend regime filter ──
    trend_sma_period: int = Field(default=200, ge=20, le=400)

    # ── RSI oscillator (entry/exit) ──
    rsi_period: int = Field(default=2, ge=1, le=50)
    rsi_oversold: float = Field(default=10.0, ge=1.0, le=49.0)   # long entry: RSI < this
    rsi_exit: float = Field(default=70.0, ge=50.0, le=99.0)      # long exit:  RSI > this

    # ── Direction toggles ──
    # The validated edge is long-only; the short side is an unvalidated mirror.
    allow_long: bool = True
    allow_short: bool = False

    # ── Stop-loss / sizing ──
    # The primary exit is the RSI snap-back. The (wide) ATR stop is a safety net
    # and the basis for risk-based position sizing.
    atr_period: int = Field(default=14, ge=2, le=100)
    sl_atr_mult: float = Field(default=4.0, ge=0.5, le=12.0)

    risk_percent: float = Field(default=0.75, ge=0.05, le=5.0)
    max_position_pct: float = Field(default=20.0, ge=1.0, le=100.0)
    max_slippage: float = Field(default=0.5, ge=0.0, le=5.0)

    # Daily bars required before the first signal (SMA period + a small buffer).
    warmup_bars: int = Field(default=210, ge=20, le=420)

    # Account / sizing context (USD). Used for position-value caps and risk math.
    account_equity: float = Field(default=100_000.0, gt=0)


def default_config() -> TripleSTConfig:
    return TripleSTConfig()
