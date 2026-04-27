"""
Paper trading position store.
In-memory dict (fast reads) + write-through to SQLite (persistence across restarts).
"""
import time
import uuid
from typing import Dict, List, Optional

from app.schemas.positions import PaperPosition, PositionStatus
from app.schemas.execution import SizedTrade
from app.schemas.directional import TradeState
from app.services import db

_positions: Dict[str, PaperPosition] = {}
_loaded = False


def _new_id() -> str:
    return uuid.uuid4().hex[:8].upper()


def bootstrap() -> None:
    """Call once at app startup to initialise SQLite and restore positions."""
    global _loaded
    if _loaded:
        return
    db.init()
    for raw in db.load_all():
        try:
            pos = PaperPosition.model_validate(raw)
            _positions[pos.id] = pos
        except Exception:
            pass
    _loaded = True


def add_position(
    underlying: str,
    sized_trade: SizedTrade,
    entry_spot_price: float,
    notes: str = "",
) -> PaperPosition:
    pos = PaperPosition(
        id=_new_id(),
        underlying=underlying,
        sized_trade=sized_trade,
        status=PositionStatus.OPEN,
        entry_timestamp_ms=int(time.time() * 1000),
        entry_spot_price=entry_spot_price,
        notes=notes,
        run_once_state=TradeState.ENTERED,
    )
    _positions[pos.id] = pos
    db.upsert(pos.model_dump())
    return pos


def get_position(pos_id: str) -> Optional[PaperPosition]:
    return _positions.get(pos_id)


def list_positions() -> List[PaperPosition]:
    return sorted(_positions.values(), key=lambda p: p.entry_timestamp_ms, reverse=True)


def update_position(pos_id: str, **kwargs) -> Optional[PaperPosition]:
    pos = _positions.get(pos_id)
    if not pos:
        return None
    updated = pos.model_copy(update=kwargs)
    _positions[pos_id] = updated
    db.upsert(updated.model_dump())
    return updated


def close_position(
    pos_id: str,
    exit_spot_price: float,
    notes: str = "",
) -> Optional[PaperPosition]:
    pos = _positions.get(pos_id)
    if not pos or pos.status == PositionStatus.CLOSED:
        return None

    structure = pos.sized_trade.structure
    spot_move = exit_spot_price - pos.entry_spot_price
    direction_sign = 1 if structure.direction.value == "long" else -1
    # Net delta accounts for both legs in spreads
    _credit = frozenset({"bull_put_spread", "bear_call_spread"})
    legs = structure.legs
    if len(legs) == 0:
        net_delta = 0.0
    elif len(legs) == 1:
        net_delta = abs(legs[0].delta)
    elif structure.structure_type in _credit:
        net_delta = max(0.0, abs(legs[1].delta) - abs(legs[0].delta))
    else:
        net_delta = max(0.0, abs(legs[0].delta) - abs(legs[1].delta))
    raw_pnl = spot_move * direction_sign * pos.sized_trade.contracts * net_delta
    max_risk = pos.sized_trade.max_risk_usd
    max_gain = structure.max_gain
    bounded = max(-max_risk, raw_pnl)
    if max_gain is not None:
        bounded = min(max_gain * pos.sized_trade.contracts, bounded)
    estimated_pnl = round(bounded, 2)

    return update_position(
        pos_id,
        status=PositionStatus.CLOSED,
        exit_timestamp_ms=int(time.time() * 1000),
        exit_spot_price=exit_spot_price,
        realized_pnl_usd=estimated_pnl,
        notes=notes or pos.notes,
        run_once_state=TradeState.EXITED,
    )


def partial_close_position(pos_id: str) -> Optional[PaperPosition]:
    """Transition OPEN → PARTIALLY_CLOSED when a partial-profit signal fires."""
    pos = _positions.get(pos_id)
    if not pos or pos.status != PositionStatus.OPEN:
        return None
    return update_position(
        pos_id,
        status=PositionStatus.PARTIALLY_CLOSED,
        run_once_state=TradeState.PARTIALLY_REDUCED,
    )


def delete_position(pos_id: str) -> bool:
    if pos_id not in _positions:
        return False
    del _positions[pos_id]
    db.remove(pos_id)
    return True


def open_count() -> int:
    return sum(1 for p in _positions.values() if p.status == PositionStatus.OPEN)


def closed_count() -> int:
    return sum(1 for p in _positions.values() if p.status == PositionStatus.CLOSED)
