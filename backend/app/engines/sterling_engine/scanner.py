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

import re
import time
from typing import List

import numpy as np

from app.engines.sterling_engine.config import EngineConfig as ScalpingConfig, ScalpingProfile
from app.engines.sterling_engine.levels import detect_levels
from app.engines.sterling_engine.schemas import ScalpingSignal, ScalpingScanResponse, SupportResistanceLevel
from app.engines.sterling_engine.price_action import evaluate_price_action
from app.engines.sterling_engine.smc import evaluate_smc
from app.engines.sterling_engine.ma_crossover import evaluate_ma_crossover
from app.engines.sterling_engine.mean_reversion import evaluate_mean_reversion
from app.engines.sterling_engine.breakout import evaluate_breakout
from app.engines.sterling_engine.delta_gamma import evaluate_delta_gamma
from app.engines.sterling_engine.whitelist_manager import is_whitelisted


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


def _macro_regime(closes_4h: np.ndarray, cfg: ScalpingProfile) -> str:
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


_MACRO_4H_RE = re.compile(r"\b4H\b")


def _relabel_macro_tf(reason: str, macro_tf: str) -> str:
    """Per-strategy reason strings hardcode "4H" as the macro-structure timeframe
    (legacy: macro was always 4h). Relabel to the profile's ACTUAL macro TF so the
    displayed reason matches where levels were really detected (e.g. 1H / 15M / 1D)."""
    label = (macro_tf or "4h").upper()
    if label == "4H" or not reason:
        return reason
    return _MACRO_4H_RE.sub(label, reason)


def scan_symbol(
    underlying: str,
    candles_4h: list,
    candles_15m: list,
    candles_1h: list,
    cfg: ScalpingProfile,
    warmup_bars_macro: int,
    warmup_bars_exec: int,
    profile_name: str = "",
    tradeable: bool = False,
    use_optimized: bool = False,
) -> List[ScalpingSignal]:
    """Evaluate all enabled strategies for one symbol."""
    now_ms = int(time.time() * 1000)

    if len(candles_4h) < warmup_bars_macro or len(candles_15m) < warmup_bars_exec:
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
            profile=profile_name,
            direction=norm_dir,
            near_level=sig.near_level,
            level_type=sig.level_type,
            pattern=sig.pattern,
            reason=_relabel_macro_tf(sig.reason, cfg.macro_timeframe),
            entry=sig.entry,
            stop_loss=sig.stop_loss,
            take_profit=sig.take_profit,
            tp_source=getattr(sig, "tp_source", ""),
            risk_pct=round(abs(sig.entry - sig.stop_loss) / sig.entry * 100, 2)
                     if has_plan and sig.entry_ok and sig.entry and sig.stop_loss
                     else None,
            leverage=None,
            size_units=None,
            notional_usd=None,
            entry_ok=sig.entry_ok,
            executable=sig.entry_ok and tradeable and not is_watch,
            timestamp_ms=now_ms,
        )

    use_opt = use_optimized

    if cfg.enable_price_action:
        if not use_opt or is_whitelisted("price_action", underlying, cfg.execution_timeframe):
            pa = evaluate_price_action(underlying, candles_4h, candles_15m, levels, cfg)
            signals.append(_make_signal(pa, "price_action"))

    if cfg.enable_smc:
        if not use_opt or is_whitelisted("smc", underlying, cfg.execution_timeframe):
            smc_sig = evaluate_smc(underlying, candles_4h, candles_15m, levels, cfg)
            signals.append(_make_signal(smc_sig, "smc"))

    if getattr(cfg, "enable_ma_crossover", False):
        if not use_opt or is_whitelisted("ma_crossover", underlying, cfg.execution_timeframe):
            ma = evaluate_ma_crossover(underlying, candles_4h, candles_15m, candles_1h, levels, cfg)
            signals.append(_make_signal(ma, "ma_crossover"))

    if getattr(cfg, "enable_mean_reversion", False):
        if not use_opt or is_whitelisted("mean_reversion", underlying, cfg.execution_timeframe):
            mr = evaluate_mean_reversion(underlying, candles_4h, candles_15m, levels, cfg)
            signals.append(_make_signal(mr, "mean_reversion"))

    if getattr(cfg, "enable_breakout", False):
        if not use_opt or is_whitelisted("breakout", underlying, cfg.execution_timeframe):
            bo = evaluate_breakout(underlying, candles_4h, candles_15m, levels, cfg)
            signals.append(_make_signal(bo, "breakout"))

    if getattr(cfg, "enable_delta_gamma", False):
        if not use_opt or is_whitelisted("delta_gamma", underlying, cfg.execution_timeframe):
            dg = evaluate_delta_gamma(underlying, candles_4h, candles_15m, levels, cfg)
            signals.append(_make_signal(dg, "delta_gamma"))

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
    candles_by_res: dict,
    cfg: ScalpingConfig,
    tradeable_set: set,
) -> ScalpingScanResponse:
    """Scan all symbols across all enabled active profiles and their strategies."""
    now_ms = int(time.time() * 1000)
    all_signals: List[ScalpingSignal] = []
    all_levels: List[SupportResistanceLevel] = []

    for sym in universe:
        tradeable = sym in tradeable_set
        
        # Deduplicate levels processing (compute levels on the macro timeframe of the first active profile)
        # Assuming the first active profile dictates the primary structure TF for levels.
        levels_computed = False
        sym_levels = []
        
        for profile_id in cfg.active_profiles:
            profile = cfg.profiles.get(profile_id)
            if not profile:
                continue
                
            macro_tf = profile.macro_timeframe or "4h"
            exec_tf = profile.execution_timeframe or "15m"
            
            c_macro = candles_by_res.get(macro_tf, {}).get(sym, [])
            c_exec = candles_by_res.get(exec_tf, {}).get(sym, [])
            c_1h = candles_by_res.get("1h", {}).get(sym, [])
            
            if not c_macro or not c_exec:
                continue
                
            if not levels_computed and len(c_macro) >= cfg.warmup_bars_4h:
                highs_4h = np.array([c.high for c in c_macro], dtype=np.float64)
                lows_4h = np.array([c.low for c in c_macro], dtype=np.float64)
                closes_4h = np.array([c.close for c in c_macro], dtype=np.float64)
                ts_4h = np.array([c.timestamp_ms for c in c_macro], dtype=np.int64)
                
                levels = detect_levels(highs_4h, lows_4h, closes_4h, ts_4h, profile)
                sym_levels = levels
                all_levels.extend([_level_to_schema(l, sym) for l in levels])
                levels_computed = True
                
            sigs = scan_symbol(
                sym, 
                c_macro, 
                c_exec, 
                c_1h,
                profile, 
                warmup_bars_macro=cfg.warmup_bars_4h,
                warmup_bars_exec=cfg.warmup_bars_15m,
                profile_name=profile_id, 
                tradeable=tradeable,
                use_optimized=cfg.use_optimized
            )
            all_signals.extend(sigs)

    # Dedup logic: Only keep one active watch/armed signal per symbol + strategy (prioritize fastest TF)
    dedup = {}
    for s in all_signals:
        key = (s.underlying, s.strategy)
        if key not in dedup:
            dedup[key] = s
        else:
            # If both are armed, keep the one with better risk/reward or the aggressive one
            if s.entry_ok and not dedup[key].entry_ok:
                dedup[key] = s
    
    all_signals = list(dedup.values())
    
    # Sort signals
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