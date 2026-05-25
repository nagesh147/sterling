"""Per-bar decision engine for the daily SMA/EMA + RSI/ADX strategy.

Pure, side-effect-free functions over a precomputed `Features` bundle. The same
primitives power both the live `/evaluate` endpoint and the historical
`backtest` replay, so what you backtest is exactly what trades.

Rule (1D timeframe)
-------------------
    Long  entry : close > SMA and close > EMA and RSI > ADX
    Long  exit  : RSI < ADX
    Short entry : close < SMA and close < EMA and RSI < ADX   (mirror)
    Short exit  : RSI > ADX                                   (mirror)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.engines.triple_st.config import TripleSTConfig
from app.engines.triple_st.features import Features


MAX_LEVERAGE = 25.0


# ─────────────────────────────────────────────────────────────────────────────
# Per-bar signal
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class BarSignal:
    i: int
    timestamp_ms: int
    direction: int            # +1 long / -1 short / 0 flat — the armed signal
    close: float
    sma: float
    ema: float
    rsi: float
    adx: float
    above_sma: bool           # close > SMA
    above_ema: bool           # close > EMA
    rsi_gt_adx: bool          # RSI > ADX
    long_ok: bool             # all three long conditions met (+ long enabled)
    short_ok: bool            # all three short conditions met (+ short enabled)
    reason: str


def evaluate_at(feat: Features, i: int, cfg: TripleSTConfig) -> BarSignal:
    """Evaluate entry readiness at the (closed) daily bar `i`."""
    close = float(feat.close[i])
    sma = float(feat.sma[i])
    ema = float(feat.ema[i])
    rsi = float(feat.rsi[i])
    adx = float(feat.adx[i])

    above_sma = close > sma
    above_ema = close > ema
    rsi_gt_adx = rsi > adx

    long_ok = cfg.allow_long and above_sma and above_ema and rsi_gt_adx
    short_ok = cfg.allow_short and (not above_sma) and (not above_ema) and (not rsi_gt_adx)

    direction = 1 if long_ok else -1 if short_ok else 0

    if direction == 1:
        reason = "long armed (C>SMA, C>EMA, RSI>ADX)"
    elif direction == -1:
        reason = "short armed (C<SMA, C<EMA, RSI<ADX)"
    else:
        misses = []
        # Frame the misses against the side the price trend favours.
        if above_sma or above_ema:
            if not above_sma:
                misses.append("close≤SMA")
            if not above_ema:
                misses.append("close≤EMA")
            if not rsi_gt_adx:
                misses.append("RSI≤ADX")
            reason = "no long: " + (", ".join(misses) if misses else "blocked")
        else:
            if above_sma:
                misses.append("close≥SMA")
            if above_ema:
                misses.append("close≥EMA")
            if rsi_gt_adx:
                misses.append("RSI≥ADX")
            reason = "no short: " + (", ".join(misses) if misses else "blocked")

    return BarSignal(
        i=i, timestamp_ms=int(feat.ts[i]), direction=direction,
        close=close, sma=sma, ema=ema, rsi=rsi, adx=adx,
        above_sma=above_sma, above_ema=above_ema, rsi_gt_adx=rsi_gt_adx,
        long_ok=long_ok, short_ok=short_ok, reason=reason,
    )


def should_exit(feat: Features, i: int, direction: int) -> bool:
    """Signal exit for an open position: the RSI/ADX momentum condition flips.

    Long  exits on RSI < ADX; short exits on RSI > ADX.
    """
    rsi = float(feat.rsi[i])
    adx = float(feat.adx[i])
    if direction == 1:
        return rsi < adx
    if direction == -1:
        return rsi > adx
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Risk-based trade plan
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TradePlan:
    direction: str                 # "long" | "short"
    entry: float
    stop_loss: float
    r_distance: float              # price distance of 1R (= stop distance)
    size_units: float              # base-asset units
    notional_usd: float
    risk_usd: float
    risk_pct: float                # % of equity at risk
    leverage: float


def build_trade_plan(feat: Features, i: int, direction: int, cfg: TripleSTConfig) -> TradePlan:
    """Risk-first sizing: a full ATR stop = exactly 1R = `risk_usd`.

    Notional follows from the stop distance; `max_position_pct` is the margin
    budget and the implied leverage is capped at `MAX_LEVERAGE`. When the cap
    binds we scale the position down and report the reduced actual risk so R
    stays honest. The strategy's real exit is the RSI/ADX flip — this stop is a
    safety net and the sizing anchor only.
    """
    entry = float(feat.close[i])
    atr = max(float(feat.atr[i]), entry * 1e-4)      # guard zero-ATR warmup
    stop_dist = cfg.sl_atr_mult * atr
    long = direction == 1
    stop_loss = entry - stop_dist if long else entry + stop_dist

    risk_pct = cfg.risk_percent
    risk_usd = cfg.account_equity * (risk_pct / 100.0)

    size_units = risk_usd / stop_dist if stop_dist > 0 else 0.0
    notional = size_units * entry
    margin_budget = max(1.0, cfg.account_equity * (cfg.max_position_pct / 100.0))
    leverage = notional / margin_budget
    if leverage > MAX_LEVERAGE:
        scale = MAX_LEVERAGE / leverage
        size_units *= scale
        notional *= scale
        leverage = MAX_LEVERAGE
        risk_usd = size_units * stop_dist            # actual risk after the cap
        risk_pct = risk_usd / cfg.account_equity * 100.0
    leverage = max(1.0, leverage)

    return TradePlan(
        direction="long" if long else "short",
        entry=round(entry, 4), stop_loss=round(stop_loss, 4),
        r_distance=round(stop_dist, 6),
        size_units=round(size_units, 6), notional_usd=round(notional, 2),
        risk_usd=round(risk_usd, 2), risk_pct=round(risk_pct, 4),
        leverage=round(leverage, 2),
    )


def warmup_ok(feat: Features, i: int, cfg: TripleSTConfig) -> bool:
    """True once every indicator at bar `i` is past its warm-up (non-zero)."""
    return (
        i >= cfg.warmup_bars
        and float(feat.sma[i]) > 0
        and float(feat.ema[i]) > 0
        and float(feat.atr[i]) > 0
    )
