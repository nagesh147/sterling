"""``SterlingKiteEngine`` — StrategyProtocol-conforming options engine.

Broker/market-agnostic: takes a series of CLOSED candles, returns ``Signal``s.
Stateful only for the trailing lifecycle (one open position per underlying).
Makes no order calls and imports no other engine's strategy logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

from app.domain.models import Candle, Signal
from app.engines.common.exit_counter import (
    get_exit_threshold, should_exit_on_reds, get_exit_reason, exit_needs_counter_signal
)
from app.engines.common.trailing import ratchet_trail
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.exits import resolve_exit, ratcheted_trail_level, reported_trail_level
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions


@dataclass
class _OpenPos:
    direction: str  # "long" | "short"
    entry: float
    stop: float  # ratcheted trail stop
    initial_stop: float
    entry_ms: int = 0


@dataclass
class ManageResult:
    underlying: str
    stop: float
    exit: bool
    reason: Optional[str] = None
    red_count: int = 0       # how many ST lines are currently red against the position
    green_lines: int = 3     # how many ST lines are still aligned with the position


def _arrays(candles: Sequence[Candle]):
    o = np.array([c.open for c in candles], dtype=float)
    h = np.array([c.high for c in candles], dtype=float)
    l = np.array([c.low for c in candles], dtype=float)
    c = np.array([c.close for c in candles], dtype=float)
    return o, h, l, c


class SterlingKiteEngine:
    """Emits an entry Signal only when the latest closed bar is a fresh full
    alignment transition; ratchets/exits via :meth:`manage`."""

    def __init__(self, cfg: Optional[SterlingKiteEngineConfig] = None):
        self.cfg = cfg or SterlingKiteEngineConfig()
        self._positions: Dict[str, _OpenPos] = {}

    # ── entry ────────────────────────────────────────────────────────────────
    def generate(self, candles: Sequence[Candle], underlying: str = "", **_) -> List[Signal]:
        if len(candles) <= self.cfg.warmup + 1:
            return []
        if underlying in self._positions:
            return []  # one open position per underlying
        o, h, l, c = _arrays(candles)
        r = compute_regime(o, h, l, c, self.cfg)
        longs, shorts = entry_transitions(r)
        i = len(c) - 1
        if not (longs[i] or shorts[i]):
            return []  # latest closed bar is not a fresh transition
        direction = "long" if longs[i] else "short"
        trail = float(r.line(self.cfg.trail_target)[i])
        entry = float(c[i])
        self._positions[underlying] = _OpenPos(direction, entry, trail, trail, int(candles[i].timestamp_ms))
        score = self._score(r, i)
        return [Signal(
            underlying=underlying,
            direction=direction,
            instrument_type="options",
            stop_loss=trail,
            take_profit=None,
            score=score,
            strength="STRONG" if score >= 80.0 else "SIGNAL",
            source="sterling_kite_engine",
            timestamp_ms=int(candles[i].timestamp_ms),
        )]

    # ── trailing lifecycle ─────────────────────────────────────────────────────
    def manage(self, candles: Sequence[Candle], underlying: str) -> Optional[ManageResult]:
        pos = self._positions.get(underlying)
        if pos is None or len(candles) <= self.cfg.warmup + 1:
            return None
        o, h, l, c = _arrays(candles)
        r = compute_regime(o, h, l, c, self.cfg)
        i = len(c) - 1

        # ── Count how many ST lines are red (against the position) ──────────
        red_count = r.red_line_count(pos.direction, i)
        green_count = 3 - red_count

        entry_i = next((j for j, bar in enumerate(candles)
                        if int(bar.timestamp_ms) == pos.entry_ms), None)
        if entry_i is None:
            # Entry aged out of lookback: use the already-persisted stop; never loosen.
            breached = self.cfg.price_stop_exit and (
                float(l[i]) <= pos.stop if pos.direction == "long" else float(h[i]) >= pos.stop)
            if breached:
                self._positions.pop(underlying, None)
                return ManageResult(underlying, pos.stop, exit=True, reason="raw price stop",
                                    red_count=red_count, green_lines=green_count)
            entry_i = i
        longs, shorts = entry_transitions(r)
        exit_i, reason = resolve_exit(r, pos.direction, entry_i, i, self.cfg, longs, shorts)
        if exit_i is not None:
            self._positions.pop(underlying, None)
            level = reported_trail_level(r, pos.direction, entry_i, exit_i, i, self.cfg)
            return ManageResult(underlying, ratchet_trail(pos.stop, level, pos.direction), exit=True, reason=reason,
                                red_count=red_count, green_lines=green_count)
        level = ratcheted_trail_level(r, pos.direction, entry_i, i, self.cfg)
        if level > 0:
            pos.stop = ratchet_trail(pos.stop, level, pos.direction)
        return ManageResult(underlying, pos.stop, exit=False,
                            red_count=red_count, green_lines=green_count)

    def has_position(self, underlying: str) -> bool:
        return underlying in self._positions

    def _score(self, r, i: int) -> float:
        # full three-way alignment is the entry condition; fixed high conviction.
        return 85.0
