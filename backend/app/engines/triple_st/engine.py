"""Per-bar decision engine for the daily RSI(2) mean-reversion strategy.

Pure, side-effect-free functions over a precomputed `Features` bundle. The same
primitives power both the live `/evaluate` endpoint and the historical
`backtest` replay, so what you backtest is exactly what trades.

Rule (1D timeframe)
-------------------
    Long  entry : close > SMA(trend) and RSI < rsi_oversold
    Long  exit  : RSI > rsi_exit
    Short entry : close < SMA(trend) and RSI > (100 - rsi_oversold)   (mirror, opt-in)
    Short exit  : RSI < (100 - rsi_exit)
"""
from __future__ import annotations

from dataclasses import dataclass

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
    sma: float                # trend SMA
    rsi: float
    in_uptrend: bool          # close > SMA(trend)
    oversold: bool            # RSI < rsi_oversold (long trigger)
    overbought: bool          # RSI > 100 - rsi_oversold (short trigger)
    reason: str


def evaluate_at(feat: Features, i: int, cfg: TripleSTConfig) -> BarSignal:
    """Evaluate entry readiness at the (closed) daily bar `i`."""
    close = float(feat.close[i])
    sma = float(feat.sma[i])
    rsi = float(feat.rsi[i])

    in_uptrend = close > sma
    oversold = rsi < cfg.rsi_oversold
    overbought = rsi > (100.0 - cfg.rsi_oversold)

    long_ok = cfg.allow_long and in_uptrend and oversold
    short_ok = cfg.allow_short and (not in_uptrend) and overbought
    direction = 1 if long_ok else -1 if short_ok else 0

    if direction == 1:
        reason = f"long armed — uptrend & RSI {rsi:.0f} < {cfg.rsi_oversold:.0f}"
    elif direction == -1:
        reason = f"short armed — downtrend & RSI {rsi:.0f} > {100 - cfg.rsi_oversold:.0f}"
    elif in_uptrend:
        reason = (f"uptrend, waiting for dip (RSI {rsi:.0f} ≥ {cfg.rsi_oversold:.0f})"
                  if cfg.allow_long else "uptrend (long disabled)")
    else:
        reason = "downtrend — no long (below SMA trend)"

    return BarSignal(
        i=i, timestamp_ms=int(feat.ts[i]), direction=direction,
        close=close, sma=sma, rsi=rsi,
        in_uptrend=in_uptrend, oversold=oversold, overbought=overbought,
        reason=reason,
    )


def should_exit(feat: Features, i: int, direction: int, cfg: TripleSTConfig) -> bool:
    """Signal exit for an open position: the RSI snaps back.

    Long exits on RSI > rsi_exit; short exits on RSI < (100 - rsi_exit).
    """
    rsi = float(feat.rsi[i])
    if direction == 1:
        return rsi > cfg.rsi_exit
    if direction == -1:
        return rsi < (100.0 - cfg.rsi_exit)
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
    stays honest. The strategy's real exit is the RSI snap-back — this (wide)
    stop is a safety net and the sizing anchor only.
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
        and float(feat.atr[i]) > 0
    )
