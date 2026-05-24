"""STRATEGY STUB — trailing-stop logic removed in the strategy reset.

The data containers (`TrailState`, `PartialExitSignal`, `TrailUpdate`) are kept
intact because `paper_store` serialises `TrailState` to/from JSON and positions
depend on that shape. Only the decision logic in `TrailingStopEngine.update`
was stripped (preserved in git history on the `strategy-v2` branch): it now
returns a no-op update that never moves the stop, never exits, and never takes
partials.

Implement the new trailing logic in `TrailingStopEngine.update`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import List, Optional

from app.core.trading_mode import TrailMode, TradingModeConfig
from app.schemas.market import Candle


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

    def to_json(self) -> str:
        d = asdict(self)
        d["mode"] = self.mode.value
        return json.dumps(d)

    @classmethod
    def from_json(cls, s: str) -> "TrailState":
        d = json.loads(s)
        d["mode"] = TrailMode(d["mode"])
        # Back-compat: older snapshots may lack newer fields
        d.setdefault("partial_25_pct", 0.10)
        d.setdefault("partial_50_pct", 0.20)
        d.setdefault("tightening_offset", 0.0)
        d.setdefault("structure_dte", None)
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
    """STUB — trailing logic removed. `update` never moves the stop or exits."""

    def update(
        self,
        state: TrailState,
        candles: List[Candle],
        st_value: float,
        direction: str,
        entry_price: float,
        mode: TradingModeConfig,
        initial_tp: Optional[float] = None,
    ) -> TrailUpdate:
        return TrailUpdate(
            new_stop=state.current_stop,
            partial=None,
            stopped_out=False,
            stop_moved=False,
            current_tp=initial_tp,
        )
