"""Multi-symbol scanner — orchestrates all 3 scalping strategies.

Runs the 4H level detector, then evaluates each strategy on every symbol
in the universe. Returns a merged list of `ScalpingSignal`s sorted by
priority (armed first, then proximity to a level).

Direction values:
  "long" / "short"       — confirmed signal, entry_ok=True
  "watch_long" / "watch_short" — MAs aligned near a level, awaiting trigger, entry_ok=True
  "none"                 — no actionable signal
"""
from __future__ import annotations

import time
from typing import List

import numpy as np

from app.engines.scalping.config import EngineConfig as ScalpingConfig
from app.engines.scalping.levels import detect_levels
from app.engines.scalping.schemas import ScalpingSignal, ScalpingScanResponse, SupportResistanceLevel
from app.engines.scalping.price_action import evaluate_price_action
from app.engines.scalping.smc import evaluate_smc
from app.engines.scalping.ma_crossover import evaluate_ma_crossover


def _level_to_schema(l, underlying: str = "") -> SupportResistanceLevel:
    return SupportResistanceLevel(
        underlying=underlying,
        price=l.price, touches=l.touches,
        first_touch_ts=l.first_touch_ts, last_touch_ts=l.last_touch_ts,
        level_type=l.level_type,
    )


def _ema_last(closes: np.ndarray, period: int) -> float:
    """Latest EMA value over `closes` (iterative; seeded with the first close)."""
    if len(closes) == 0:
        return 0.0
    k = 2.0 / (period + 1)
    e = float(closes[0])
    for x in closes[1:]:
        e = k * float(x) + (1 - k) * e
    return e


def _macro_regime(closes_4h: np.ndarray, cfg: ScalpingConfig) -> str:
    """4H trend regime: 'bull' | 'bear' | 'chop' from EMA(fast) vs EMA(slow)."""
    if len(closes_4h) < cfg.macro_trend_ema_slow:
        return "chop"
    fast = _ema_last(closes_4h, cfg.macro_trend_ema_fast)
    slow = _ema_last(closes_4h, cfg.macro_trend_ema_slow)
    last = float(closes_4h[-1]) or 1.0
    spread = (fast - slow) / last
    band = cfg.macro_trend_flat_band_pct / 100.0
    if spread > band:
        return "bull"
    if spread < -band:
        return "bear"
    return "chop"


def _is_counter_trend(direction: str, regime: str) -> bool:
    """A long in a downtrend / a short in an uptrend (chop is never counter-trend)."""
    return (direction == "long" and regime == "bear") or (direction == "short" and regime == "bull")


# Normalize watch_long/watch_short to long/short for the API
def _normalize_direction(d: str) -> str:
    if d in ("watch_long",):
        return "long"
    if d in ("watch_short",):
        return "short"
    return d


def scan_symbol(
    underlying: str,
    candles_4h: list,
    candles_15m: list,
    cfg: ScalpingConfig,
    tradeable: bool = False,
) -> List[ScalpingSignal]:
    """Evaluate all enabled strategies for one symbol."""
    now_ms = int(time.time() * 1000)

    if len(candles_4h) < cfg.warmup_bars_4h or len(candles_15m) < cfg.warmup_bars_15m:
        return [ScalpingSignal(
            underlying=underlying, strategy="none", direction="none",
            close=float(candles_15m[-1].close) if candles_15m else 0,
            reason="insufficient data", entry_ok=False, executable=False,
            timestamp_ms=now_ms,
        )]

    highs_4h = np.array([c.high for c in candles_4h], dtype=np.float64)
    lows_4h = np.array([c.low for c in candles_4h], dtype=np.float64)
    closes_4h = np.array([c.close for c in candles_4h], dtype=np.float64)
    ts_4h = np.array([c.timestamp_ms for c in candles_4h], dtype=np.int64)

    levels = detect_levels(highs_4h, lows_4h, closes_4h, ts_4h, cfg)

    signals: List[ScalpingSignal] = []

    def _make_signal(sig, strategy: str) -> ScalpingSignal:
        norm_dir = _normalize_direction(sig.direction)
        has_plan = norm_dir in ("long", "short") and sig.entry is not None
        is_watch = "Watching" in sig.reason or "awaiting" in sig.reason
        return ScalpingSignal(
            underlying=underlying,
            close=float(candles_15m[-1].close),
            strategy=strategy,
            direction=norm_dir,
            near_level=sig.near_level,
            level_type=sig.level_type,
            pattern=sig.pattern,
            reason=sig.reason,
            entry=sig.entry,
            stop_loss=sig.stop_loss,
            take_profit=sig.take_profit,
            tp_source=getattr(sig, "tp_source", ""),
            risk_pct=round(cfg.risk_percent, 2) if has_plan and sig.entry_ok else None,
            leverage=None,
            size_units=None,
            notional_usd=None,
            entry_ok=sig.entry_ok,
            executable=sig.entry_ok and tradeable and not is_watch,
            timestamp_ms=now_ms,
        )

    if cfg.enable_price_action:
        pa = evaluate_price_action(underlying, candles_4h, candles_15m, levels, cfg)
        signals.append(_make_signal(pa, "price_action"))

    if cfg.enable_smc:
        smc_sig = evaluate_smc(underlying, candles_4h, candles_15m, levels, cfg)
        signals.append(_make_signal(smc_sig, "smc"))

    if cfg.enable_ma_crossover:
        ma = evaluate_ma_crossover(underlying, candles_4h, candles_15m, levels, cfg)
        signals.append(_make_signal(ma, "ma_crossover"))

    # Opt-in macro-trend filter: drop counter-trend setups (long in a 4H downtrend,
    # short in an uptrend). Stats show trend-aligned setups carry a higher PF, but
    # counter-trend is still +EV — so this is off by default and trades total
    # return for per-trade quality / lower variance when enabled.
    if cfg.macro_trend_filter:
        regime = _macro_regime(closes_4h, cfg)
        if regime in ("bull", "bear"):
            signals = [s for s in signals if not _is_counter_trend(s.direction, regime)]

    return signals


def scan_universe(
    universe: List[str],
    candles_4h_map: dict,
    candles_15m_map: dict,
    cfg: ScalpingConfig,
    tradeable_set: set,
) -> ScalpingScanResponse:
    """Scan all symbols across all enabled strategies."""
    now_ms = int(time.time() * 1000)
    all_signals: List[ScalpingSignal] = []
    all_levels: List[SupportResistanceLevel] = []

    for sym in universe:
        c4h = candles_4h_map.get(sym, [])
        c15m = candles_15m_map.get(sym, [])
        if not c4h or not c15m:
            continue
        tradeable = sym in tradeable_set
        sigs = scan_symbol(sym, c4h, c15m, cfg, tradeable=tradeable)
        all_signals.extend(sigs)

        closes_4h = np.array([c.close for c in c4h], dtype=np.float64)
        highs_4h = np.array([c.high for c in c4h], dtype=np.float64)
        lows_4h = np.array([c.low for c in c4h], dtype=np.float64)
        ts_4h = np.array([c.timestamp_ms for c in c4h], dtype=np.int64)
        for lvl in detect_levels(highs_4h, lows_4h, closes_4h, ts_4h, cfg):
            all_levels.append(_level_to_schema(lvl, sym))

    # Armed signals first, then by direction (long > short > none)
    all_signals.sort(key=lambda s: (
        0 if s.entry_ok else 1,
        0 if s.direction == "long" else 1 if s.direction == "short" else 2,
    ))

    armed = sum(1 for s in all_signals if s.entry_ok)

    return ScalpingScanResponse(
        signals=all_signals,
        levels=all_levels,
        count=len(all_signals),
        armed_count=armed,
        timestamp_ms=now_ms,
    )