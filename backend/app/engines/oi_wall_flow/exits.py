"""Where an OI Wall Flow trade stops.

Two independent kills:

1. Premium stop — the option itself lost ``stop_premium_pct``.
2. Wall invalidation — spot printed through the opposing OI wall, so the
   chain thesis is dead even if the premium has not caught up yet.

Targets are premium percentages. The second target is a runner; the first is
the scale the BSE 3500 CE plan used.
"""
from __future__ import annotations

from typing import Optional

from .config import OIWallFlowConfig
from .models import PositionState, q2


def should_exit(pos: PositionState, premium: float, spot: float,
                cfg: OIWallFlowConfig) -> Optional[str]:
    if premium > 0 and pos.stop > 0 and premium <= pos.stop:
        return "stop"
    if pos.target is not None and premium > 0 and premium >= pos.target:
        return "target"
    if cfg.wall_invalidation and spot > 0 and pos.underlying_invalidation > 0:
        if pos.option_type == "CE" and spot < pos.underlying_invalidation:
            return "put_wall_broken"
        if pos.option_type == "PE" and spot > pos.underlying_invalidation:
            return "call_wall_broken"
    return None


def realised_inr(pos: PositionState, exit_price: float) -> float:
    return q2((exit_price - pos.entry) * pos.quantity)
