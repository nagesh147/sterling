"""
Session-scoped P&L snapshot history per paper position.
Recorded each time a position is monitored.
"""
from collections import deque
from typing import Dict, Deque, List, Optional
from pydantic import BaseModel

MAX_SNAPSHOTS = 200


class PnLSnapshot(BaseModel):
    timestamp_ms: int
    spot_price: float
    estimated_pnl: float
    current_dte: int


_history: Dict[str, Deque[PnLSnapshot]] = {}


def record(pos_id: str, spot: float, estimated_pnl: float, dte: int, timestamp_ms: int) -> None:
    if pos_id not in _history:
        _history[pos_id] = deque(maxlen=MAX_SNAPSHOTS)
    _history[pos_id].append(PnLSnapshot(
        timestamp_ms=timestamp_ms,
        spot_price=spot,
        estimated_pnl=estimated_pnl,
        current_dte=dte,
    ))


def get_history(pos_id: str) -> List[PnLSnapshot]:
    return list(_history.get(pos_id, []))


def clear(pos_id: Optional[str] = None) -> None:
    if pos_id:
        _history.pop(pos_id, None)
    else:
        _history.clear()
