"""STRATEGY STUB — triple-barrier labelling removed in the strategy reset.

Preserved in git history on the `strategy-v2` branch. The data containers
(`BarrierParams`, `LabelledEvent`) and function signatures are kept so the
analytics-baseline endpoint imports cleanly; `triple_barrier_labels` returns no
events so the label distribution is empty.

Implement the new labelling logic here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from app.schemas.market import Candle


@dataclass(frozen=True)
class BarrierParams:
    pt_mult: float = 2.0
    sl_mult: float = 1.0
    max_hold_bars: int = 24
    vol_lookback: int = 14


@dataclass
class LabelledEvent:
    bar_idx: int
    label: int
    horizon_bars: int
    barrier_hit: str
    entry_price: float
    realized_return: float
    features: Dict[str, Any] = field(default_factory=dict)


def triple_barrier_labels(
    candidates: Sequence[Dict[str, Any]],
    candles: Sequence[Candle],
    *,
    params: Optional[BarrierParams] = None,
) -> List[LabelledEvent]:
    """Neutral: produce no labelled events (no strategy loaded)."""
    return []


def label_distribution(events: Sequence[LabelledEvent]) -> Dict[str, int]:
    out = {"pt": 0, "sl": 0, "vert": 0, "n": len(list(events))}
    for e in events:
        if e.label == 1:
            out["pt"] += 1
        elif e.label == -1:
            out["sl"] += 1
        else:
            out["vert"] += 1
    return out
