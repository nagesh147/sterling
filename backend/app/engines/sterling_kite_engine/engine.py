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
from app.engines.sterling_kite_engine.config import SterlingKiteEngineConfig
from app.engines.sterling_kite_engine.regime import compute_regime, entry_transitions


@dataclass
class _OpenPos:
    direction: str  # "long" | "short"
    entry: float
    stop: float  # ratcheted trail stop
    initial_stop: float


@dataclass
class ManageResult:
    underlying: str
    stop: float
    exit: bool
    reason: Optional[str] = None


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
        self._positions[underlying] = _OpenPos(direction, entry, trail, trail)
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
        line = float(r.line(self.cfg.trail_target)[i])
        trend = int(r.trend(self.cfg.trail_target)[i])

        if pos.direction == "long":
            pos.stop = max(pos.stop, line)  # ratchet up only
            flipped = trend == -1
        else:
            pos.stop = min(pos.stop, line)  # ratchet down only
            flipped = trend == 1

        # The trail-target flip is the SOLE exit. (A former "early-lock" branch that
        # also honored a slow-ST flip once in profit was removed: the slow ST is the
        # widest band, so it always flips *after* the trail_target — it changed zero
        # trades across 7.5y of real data. See study/kite_st_exit_analysis.md.)
        if flipped:
            self._positions.pop(underlying, None)
            return ManageResult(underlying, pos.stop, exit=True, reason="trail_flip")
        return ManageResult(underlying, pos.stop, exit=False)

    def has_position(self, underlying: str) -> bool:
        return underlying in self._positions

    def _score(self, r, i: int) -> float:
        # full three-way alignment is the entry condition; fixed high conviction.
        return 85.0
