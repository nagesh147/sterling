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
    trail_mode_name: str | None = None,
    trail_atr_mult: float = 2.0,
    is_paper: bool = True,
    initial_sl: float | None = None,
    initial_tp: float | None = None,
) -> PaperPosition:
    from app.core.trading_mode import MODES, DEFAULT_MODE, TrailMode
    from app.engines.directional.trailing_stop import TrailState

    mode_name = trail_mode_name or DEFAULT_MODE
    mode      = MODES.get(mode_name, MODES[DEFAULT_MODE])

    # Use ATR-based SL when provided; direction-aware fallback (long: below entry, short: above)
    if initial_sl is not None:
        sl_price = initial_sl
    else:
        _dir = sized_trade.structure.direction.value if sized_trade else "long"
        sl_price = (entry_spot_price * 0.95 if _dir == "long"
                    else entry_spot_price * 1.05)

    trail_state = TrailState(
        mode=mode.trail_mode,
        current_stop=sl_price,
        highest_seen=entry_spot_price,
        lowest_seen=entry_spot_price,
        trail_mult=mode.trail_atr_mult,
        partial_25_pct=mode.partial_25_pct,
        partial_50_pct=mode.partial_50_pct,
    )

    pos = PaperPosition(
        id=_new_id(),
        underlying=underlying,
        sized_trade=sized_trade,
        status=PositionStatus.OPEN,
        entry_timestamp_ms=int(time.time() * 1000),
        entry_spot_price=entry_spot_price,
        notes=notes,
        run_once_state=TradeState.ENTERED,
        trail_stop_json=trail_state.to_json(),
        trail_mode=mode.trail_mode.value,
        entry_price_real=entry_spot_price,
        is_paper=is_paper,
        initial_sl=round(sl_price, 4),
        current_sl=round(sl_price, 4),
        initial_tp=round(initial_tp, 4) if initial_tp is not None else None,
        current_tp=round(initial_tp, 4) if initial_tp is not None else None,
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
    # All spread types: legs[0] has higher |delta| → net = legs[0]|Δ| - legs[1]|Δ|
    legs = structure.legs
    if len(legs) == 0:
        net_delta = 0.0
    elif len(legs) == 1:
        net_delta = abs(legs[0].delta)
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


def partial_close_position(
    pos_id: str,
    exit_spot_price: float = 0.0,
    partial_ratio: float = 0.50,
) -> Optional[PaperPosition]:
    """
    Close `partial_ratio` of the position.
    Reduces contracts proportionally, books partial realized P&L,
    transitions to PARTIALLY_CLOSED.
    """
    pos = _positions.get(pos_id)
    if not pos or pos.status != PositionStatus.OPEN:
        return None

    structure      = pos.sized_trade.structure
    direction_sign = 1 if structure.direction.value == "long" else -1
    legs           = structure.legs
    if not legs:
        net_delta = 0.0
    elif len(legs) == 1:
        net_delta = abs(legs[0].delta)
    else:
        net_delta = max(0.0, abs(legs[0].delta) - abs(legs[1].delta))

    closed_contracts    = max(1, round(pos.sized_trade.contracts * partial_ratio))
    remaining_contracts = max(0, pos.sized_trade.contracts - closed_contracts)

    spot_move   = (exit_spot_price - pos.entry_spot_price) if exit_spot_price > 0 else 0.0
    raw_pnl     = spot_move * direction_sign * closed_contracts * net_delta
    risk_closed = pos.sized_trade.max_risk_usd * partial_ratio
    partial_pnl = max(-risk_closed, raw_pnl)
    if structure.max_gain is not None:
        partial_pnl = min(structure.max_gain * closed_contracts, partial_pnl)
    partial_pnl = round(partial_pnl, 2)

    scale     = 1.0 - partial_ratio
    new_sized = pos.sized_trade.model_copy(update={
        "contracts":           remaining_contracts,
        "max_risk_usd":        round(pos.sized_trade.max_risk_usd        * scale, 2),
        "position_value":      round(pos.sized_trade.position_value      * scale, 2),
        "capital_at_risk_pct": round(pos.sized_trade.capital_at_risk_pct * scale, 3),
    })

    prev_realized = pos.realized_pnl_usd or 0.0
    return update_position(
        pos_id,
        status=PositionStatus.PARTIALLY_CLOSED,
        run_once_state=TradeState.PARTIALLY_REDUCED,
        sized_trade=new_sized,
        realized_pnl_usd=round(prev_realized + partial_pnl, 2),
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
