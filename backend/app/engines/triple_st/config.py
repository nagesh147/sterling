"""Configuration for the daily SMA/EMA + RSI/ADX strategy.

A deliberately small surface. The strategy has only a handful of knobs: the
four indicator periods, the direction toggles, and the risk/sizing inputs used
to turn a raw signal into an executable trade plan.

Strategy rule (1D timeframe)
----------------------------
    Long  entry : close > SMA(sma_period) and close > EMA(ema_period)
                  and RSI(rsi_period) > ADX(adx_period)
    Long  exit  : RSI(rsi_period) < ADX(adx_period)

    Short entry : close < SMA and close < EMA and RSI < ADX   (mirror)
    Short exit  : RSI > ADX                                    (mirror)

The SMA(50)/EMA(7)/RSI(2)/ADX(2) defaults match the spec; everything is
centralised here so a single edit re-tunes the whole pipeline.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class TripleSTConfig(BaseModel):
    """Operator-facing config bundle. Echoed in every evaluation/backtest
    response so the UI always renders against the exact parameters used.
    """

    # Primary timeframe — the rule is defined on daily candles.
    timeframe: str = "1d"

    # ── Indicator periods (defaults match the spec) ──
    sma_period: int = Field(default=50, ge=2, le=400)
    ema_period: int = Field(default=7, ge=2, le=200)
    rsi_period: int = Field(default=2, ge=1, le=50)
    adx_period: int = Field(default=2, ge=1, le=50)

    # ── Direction toggles ──
    # The spec is long-only; the short side is a symmetric mirror, opt-out here.
    allow_long: bool = True
    allow_short: bool = True

    # ── Stop-loss / sizing ──
    # The strategy's primary exit is the RSI/ADX flip. The ATR stop is a
    # risk-defining safety net and the basis for risk-based position sizing.
    atr_period: int = Field(default=14, ge=2, le=100)
    sl_atr_mult: float = Field(default=2.5, ge=0.5, le=10.0)

    risk_percent: float = Field(default=0.75, ge=0.05, le=5.0)
    max_position_pct: float = Field(default=20.0, ge=1.0, le=100.0)
    max_slippage: float = Field(default=0.5, ge=0.0, le=5.0)

    # Daily bars required before the first signal (SMA period + a small buffer).
    warmup_bars: int = Field(default=60, ge=10, le=400)

    # Account / sizing context (USD). Used for position-value caps and risk math.
    account_equity: float = Field(default=100_000.0, gt=0)


def default_config() -> TripleSTConfig:
    return TripleSTConfig()
