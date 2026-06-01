"""Trailing-stop engine — active for every monitored position (scalping included).

`TrailingStopEngine.update` implements an ATR / percentage / supertrend / hybrid trailing
stop with a breakeven lock and a monotonic ratchet (the stop only ever moves in
the trade's favour). It is wired in three places:
  • `add_position` attaches a `TrailState` at entry (scalping positions use the
    "scalping" mode's PERCENTAGE trail).
  • `_background_position_monitor` (main.py) calls `update` every poll on 15m
    candles for scalping positions / 1H for directional, persists the new stop,
    and amends the live exchange stop via cancel-replace.
  • `monitor_all` / `monitor_position` endpoints call it on demand.

`TrailState`, `PartialExitSignal`, `TrailUpdate` are serialised to/from JSON by
`paper_store`, so their shape must stay stable.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import List, Optional

from app.core.trading_mode import TrailMode, TradingModeConfig
from app.schemas.market import Candle


def realistic_stop_fill(
    stop: float, spot: float, direction_sign: int, max_slip_bps: float = 5.0,
) -> float:
    """Price to book when a stop is hit, modelling a real stop order's fill.

    The background monitor polls on an interval, so by the time it sees a
    breach the live `spot` has run past the stop. Booking the exit at that
    overshot `spot` charges the whole interval's drift as slippage — which on
    a large position turns a breakeven stop into a big loss. A real stop fills
    ~at the stop ± a few bps, so cap the booked slippage at `max_slip_bps`
    (use the smaller of the actual overshoot and the cap), direction-aware.

    `direction_sign`: +1 long (stop below, adverse = price lower),
                      −1 short (stop above, adverse = price higher).
    """
    cap = abs(stop) * max_slip_bps / 10_000.0
    if direction_sign >= 0:                      # long
        overshoot = max(0.0, stop - spot)        # price dropped through the stop
        return stop - min(overshoot, cap)
    overshoot = max(0.0, spot - stop)            # short: price rose through the stop
    return stop + min(overshoot, cap)


@dataclass
class TrailState:
    mode: TrailMode
    current_stop: float
    highest_seen: float
    lowest_seen: float
    partial_25_done: bool = False
    partial_50_done: bool = False
    breakeven_set: bool = False
    trail_mult: float = 2.0
    partial_25_pct: float = 0.10
    partial_50_pct: float = 0.20
    tightening_offset: float = 0.0
    structure_dte: Optional[int] = None
    # Tiered TP — persists whether the 1.5R scale-out clip has been taken
    tp1_triggered: bool = False
    # Initial risk distance (|entry − initial stop|) — lets the trail tighten and
    # lock profit by R-multiple. 0 ⇒ unknown (legacy snapshot): fall back to the
    # distance-based breakeven.
    initial_risk: float = 0.0
    timeframe: str = "intraday"

    def to_json(self) -> str:
        d = asdict(self)
        d["mode"] = self.mode.value
        return json.dumps(d)

    @classmethod
    def from_json(cls, s: str) -> "TrailState":
        d = json.loads(s)
        try:
            d["mode"] = TrailMode(d.get("mode", "atr"))
        except ValueError:
            d["mode"] = TrailMode.ATR
            
        # Back-compat: older snapshots may lack newer fields
        d.setdefault("partial_25_pct", 0.10)
        d.setdefault("partial_50_pct", 0.20)
        d.setdefault("tightening_offset", 0.0)
        d.setdefault("structure_dte", None)
        d.setdefault("tp1_triggered", False)
        d.setdefault("initial_risk", 0.0)
        d.setdefault("timeframe", "intraday")
        return cls(**d)


@dataclass
class PartialExitSignal:
    close_pct: int
    new_trail_mult: Optional[float]
    reason: str
    partial_ratio: float = 0.25


@dataclass
class TrailUpdate:
    new_stop: float
    partial: Optional[PartialExitSignal]
    stopped_out: bool
    stop_moved: bool
    current_tp: Optional[float] = None  # echoed back unchanged


class TrailingStopEngine:
    """ATR/%/supertrend/hybrid trailing stop with breakeven and a monotonic ratchet."""

    def update(
        self,
        state: TrailState,
        candles: List[Candle],
        st_value: float,
        direction: str,
        entry_price: float,
        mode: TradingModeConfig,
        initial_tp: Optional[float] = None,
        is_options: bool = False,
        iv_change: float = 0.0,
        theta_burn_high: bool = False,
        total_gex: Optional[float] = None,
    ) -> TrailUpdate:
        """ATR (or %/supertrend) trailing stop with a monotonic ratchet plus
        R-multiple profit locking — the stop only ever moves in the trade's
        favour, never loosens.

        Active for every monitored position (scalping included): `add_position`
        attaches a TrailState and the background monitor calls this each poll.
        """
        if not candles or len(candles) < 2:
            return TrailUpdate(state.current_stop, None, False, False, initial_tp)

        is_long = str(direction).lower() in ("long", "bullish", "buy")
        price = float(candles[-1].close)
        hi = float(candles[-1].high)
        lo = float(candles[-1].low)

        # ── ATR over the available candles ──────────────────────────────────
        period = min(14, len(candles) - 1)
        trs = []
        for k in range(len(candles) - period, len(candles)):
            h, l, pc = float(candles[k].high), float(candles[k].low), float(candles[k - 1].close)
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr = sum(trs) / len(trs) if trs else 0.0

        mult = state.trail_mult or getattr(mode, "trail_atr_mult", 2.0) or 2.0
        
        # Adjust base trail depending on mode
        if state.mode == TrailMode.PERCENTAGE:
            trail_dist = price * (mult / 100.0)
        else:
            # Default or ATR/Hybrid
            trail_dist = mult * atr if atr > 0 else price * 0.01
            
            # Hybrid base-trail enhancement if explicitly set or we assume options need it
            if is_options and getattr(state.mode, "value", "") == "hybrid":
                # Wider trail during high IV (IV factor logic placeholder)
                iv_factor = 0.0 if not iv_change else min(0.3, max(-0.3, iv_change))
                trail_dist = trail_dist * (1 + iv_factor)

        if trail_dist <= 0:
            trail_dist = price * 0.01

        # ── R-multiple achieved (drives tightening + profit locks) ──────────
        risk = state.initial_risk if state.initial_risk and state.initial_risk > 0 else 0.0
        profit = (price - entry_price) if is_long else (entry_price - price)
        r_mult = (profit / risk) if risk > 0 else 0.0

        # Timeframe Adaptive Logic for Progressive Tightening
        squeeze_factor = 1.0
        if risk > 0:
            if state.timeframe in ("scalping", "intraday"):
                if r_mult >= 3.0: squeeze_factor = 0.35
                elif r_mult >= 2.0: squeeze_factor = 0.5
                elif r_mult >= 1.0: squeeze_factor = 0.7
                elif r_mult >= 0.5: squeeze_factor = 0.9
            elif state.timeframe in ("overnight", "positional"):
                if r_mult >= 3.0: squeeze_factor = 0.3
                elif r_mult >= 2.0: squeeze_factor = 0.45
                elif r_mult >= 1.0: squeeze_factor = 0.65
                elif r_mult >= 0.5: squeeze_factor = 0.85
            else: # swing
                if r_mult >= 3.0: squeeze_factor = 0.25
                elif r_mult >= 2.0: squeeze_factor = 0.4
                elif r_mult >= 1.0: squeeze_factor = 0.6
                elif r_mult >= 0.5: squeeze_factor = 0.8
                
        trail_dist *= squeeze_factor

        # ── Options specific guards ─────────────────────────────────────────
        if is_options:
            if abs(iv_change) > 0.15: # IV crush or explosion implies volatility regime switch, tighten
                trail_dist *= 0.6
            if theta_burn_high:
                trail_dist *= 0.75
                
            # GEX Trailing Guard
            if total_gex is not None:
                if total_gex > 50_000:
                    # Positive GEX (pinning regime) -> tighter squeeze
                    trail_dist *= 0.80
                elif total_gex < -50_000:
                    # Negative GEX (momentum regime) -> widen trail to ride
                    trail_dist *= 1.25

        # ── Stepped profit lock — the floor the stop is pulled up to ────────
        lock: Optional[float] = None
        if risk > 0:
            if r_mult >= 1.0:
                lock = entry_price                       # breakeven at +1R
                state.breakeven_set = True
            
            # Additional locks depending on timeframe to allow intermediate scale-outs
            if state.timeframe in ("scalping", "intraday"):
                if r_mult >= 2.0:
                    step = entry_price + risk if is_long else entry_price - risk
                    lock = (max(lock, step) if is_long else min(lock, step)) if lock is not None else step
                if r_mult >= 3.0:
                    step = entry_price + 2.0 * risk if is_long else entry_price - 2.0 * risk
                    lock = (max(lock, step) if is_long else min(lock, step)) if lock is not None else step
            elif state.timeframe in ("overnight", "positional"):
                if r_mult >= 2.0:
                    step = entry_price + 1.25 * risk if is_long else entry_price - 1.25 * risk
                    lock = (max(lock, step) if is_long else min(lock, step)) if lock is not None else step
                if r_mult >= 3.0:
                    step = entry_price + 2.0 * risk if is_long else entry_price - 2.0 * risk
                    lock = (max(lock, step) if is_long else min(lock, step)) if lock is not None else step
            else: # swing
                if r_mult >= 2.0:
                    step = entry_price + 1.5 * risk if is_long else entry_price - 1.5 * risk
                    lock = (max(lock, step) if is_long else min(lock, step)) if lock is not None else step
                if r_mult >= 3.0:
                    step = entry_price + 2.5 * risk if is_long else entry_price - 2.5 * risk
                    lock = (max(lock, step) if is_long else min(lock, step)) if lock is not None else step
        else:
            ran_one_dist = (price >= entry_price + trail_dist) if is_long else (price <= entry_price - trail_dist)
            if not state.breakeven_set and ran_one_dist:
                lock = entry_price
                state.breakeven_set = True

        # ── Track the favourable extreme ────────────────────────────────────
        state.highest_seen = max(state.highest_seen or price, hi, price)
        prior_low = state.lowest_seen if (state.lowest_seen and state.lowest_seen > 0) else price
        state.lowest_seen = min(prior_low, lo, price)

        new_stop = state.current_stop
        moved = False

        if is_long:
            cand = state.highest_seen - trail_dist
            if state.mode == TrailMode.SUPERTREND and st_value and st_value > 0:
                cand = max(cand, float(st_value))
            if lock is not None:
                cand = max(cand, lock)
            if cand > new_stop:                          # ratchet up only
                new_stop, moved = cand, True
            stopped = price <= new_stop
        else:
            cand = state.lowest_seen + trail_dist
            if state.mode == TrailMode.SUPERTREND and st_value and st_value > 0:
                cand = min(cand, float(st_value))
            if lock is not None:
                cand = min(cand, lock)
            if cand < new_stop:                          # ratchet down only
                new_stop, moved = cand, True
            stopped = price >= new_stop

        state.current_stop = round(float(new_stop), 6)
        
        # Evaluate partial scale-out
        partial_exit = None
        if r_mult >= 2.0 and not state.partial_50_done:
            partial_exit = PartialExitSignal(
                close_pct=30, 
                new_trail_mult=None, 
                reason="2R Scale Out", 
                partial_ratio=0.30
            )
            state.partial_50_done = True
        elif r_mult >= 1.5 and not state.tp1_triggered:
            # 1.5R intermediate lock without closing
            state.tp1_triggered = True

        return TrailUpdate(
            new_stop=state.current_stop,
            partial=partial_exit,
            stopped_out=bool(stopped),
            stop_moved=moved,
            current_tp=initial_tp,
        )
