"""
Paper trading position store.
In-memory dict (fast reads) + write-through to SQLite (persistence across restarts).
"""
import logging
import time
import uuid
from typing import Dict, List, Optional

from app.schemas.positions import PaperPosition, PositionStatus
from app.schemas.execution import SizedTrade
from app.schemas.directional import TradeState
from app.schemas.greeks import GreeksSnapshot
from app.services import db

log = logging.getLogger(__name__)

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
    order_id: str | None = None,
    order_status: str | None = None,
    # ── Options snapshot (Phase 0). Callers entering an options trade pass
    # premium + IV + DTE + Greeks at entry so the close-out PnL uses real
    # premium arithmetic instead of delta-linear approximation, and the
    # background monitor can drive DTE force-close + Greek-aware trailing.
    entry_premium: float | None = None,
    entry_iv: float | None = None,
    entry_dte: int | None = None,
    entry_greeks_snapshot: GreeksSnapshot | None = None,
    expected_theta_burn_usd: float | None = None,
    # exit counter for unification with kite engine
    exit_mode: str = "two_red",
    current_red_count: int = 0,
    exit_threshold: int = 2,
) -> PaperPosition:
    # Issue 17 — refuse to record a position with a corrupt entry price.
    # Pre-TTACE seed data has rows where entry_spot_price == 0; tightening at
    # write-time stops the database from gaining more.
    if entry_spot_price is None or entry_spot_price <= 0:
        raise ValueError(
            f"entry_spot_price must be > 0 (got {entry_spot_price!r})"
        )

    from app.core.trading_mode import MODES, DEFAULT_MODE, TrailMode
    from app.engines.directional.trailing_stop import TrailState

    mode_name = trail_mode_name or "swing"  # hybrid enabled in swing/positional
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
        # Distance to the initial stop — drives R-multiple trail tightening / locks.
        initial_risk=abs(entry_spot_price - sl_price),
        # Hybrid support
        hybrid_atr_mult=mode.trail_atr_mult,
        hybrid_st_weight=0.5,
        hybrid_use_st=True,
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
        order_id=order_id,
        order_status=order_status,
        mode=mode_name,
        # Options snapshot fields. Auto-fall-back to first-leg mark_price /
        # mark_iv / dte if the caller didn't supply them explicitly but the
        # position is an option (structure_type != "futures"); makes the new
        # premium-based PnL math useful even for legacy entry callsites that
        # haven't been updated yet.
        entry_premium=entry_premium if entry_premium is not None else _default_entry_premium(sized_trade),
        entry_iv=entry_iv if entry_iv is not None else _default_entry_iv(sized_trade),
        entry_dte=entry_dte if entry_dte is not None else _default_entry_dte(sized_trade),
        entry_greeks_snapshot=entry_greeks_snapshot,
        expected_theta_burn_usd=expected_theta_burn_usd,
        exit_mode=exit_mode,
        current_red_count=current_red_count,
        exit_threshold=exit_threshold,
    )
    _positions[pos.id] = pos
    db.upsert(pos.model_dump())
    return pos


def _default_entry_premium(sized_trade: SizedTrade) -> Optional[float]:
    """Use leg[0].mark_price as a fallback entry premium when the caller
    didn't supply one explicitly. Returns None for futures (no premium).
    """
    s = sized_trade.structure
    if s.structure_type == "futures" or not s.legs:
        return None
    return float(s.legs[0].mark_price or s.legs[0].mid_price or 0.0)


def _default_entry_iv(sized_trade: SizedTrade) -> Optional[float]:
    s = sized_trade.structure
    if s.structure_type == "futures" or not s.legs:
        return None
    iv = float(s.legs[0].mark_iv or 0.0)
    # Adapter sometimes returns IV as a percentage (65.0 for 65%) and
    # sometimes as a decimal (0.65). Normalise to decimal.
    return iv / 100.0 if iv > 5.0 else iv


def _default_entry_dte(sized_trade: SizedTrade) -> Optional[int]:
    s = sized_trade.structure
    if s.structure_type == "futures" or not s.legs:
        return None
    return int(s.legs[0].dte or 0)


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
    *,
    exit_premium: Optional[float] = None,
    exit_reason: Optional[str] = None,
    fill_type: Optional[str] = None,
    settlement_recorded: bool = False,
) -> Optional[PaperPosition]:
    """Close a position and compute realised PnL with the correct formula
    for the instrument:

      • futures: `(exit_price − entry_price) × dir × contracts`. Leverage
        does NOT enter the PnL formula — it only affects the margin posted.
      • options: `(exit_premium − entry_premium) × contracts × multiplier`.
        Delta India BTC/ETH index options have multiplier = 1 (1 contract
        = $1 USD per $1 premium move). Callers should pass `exit_premium`
        from the live option chain; we fall back to a delta-linear
        estimate (and log a warning) when they don't.

    Prior versions over-stated futures PnL by leverage× (`net_delta = leverage`)
    and used delta-linear approximation for options (ignoring gamma/theta/vega
    drift). Both were silent live-trading bugs. See plan Phase 0.
    """
    pos = _positions.get(pos_id)
    if not pos or pos.status == PositionStatus.CLOSED:
        return None

    structure = pos.sized_trade.structure
    direction_sign = 1 if structure.direction.value == "long" else -1
    contracts = pos.sized_trade.contracts
    # qty = coin quantity = lots × lot size. PnL / value scale with qty, not the
    # raw lot count (cv defaults to 1.0 so legacy coin-based positions are
    # unchanged; a Delta ETH position of 42 lots × 0.01 moves as 0.42 ETH).
    qty = pos.sized_trade.qty
    is_futures = structure.structure_type == "futures"

    if is_futures:
        # Futures: linear PnL in spot. Leverage absent.
        spot_move = exit_spot_price - pos.entry_spot_price
        raw_pnl = spot_move * direction_sign * qty
    else:
        # Options: premium-based PnL. Multiplier = 1 for DEI BTC/ETH index opts.
        entry_premium = (
            pos.entry_premium
            if pos.entry_premium is not None
            else _default_entry_premium(pos.sized_trade) or 0.0
        )
        ex_prem = exit_premium
        if ex_prem is None:
            # Delta-linear fallback. Explicitly lossy and logged so callers
            # are nudged to supply a real exit premium from the option chain.
            spot_move = exit_spot_price - pos.entry_spot_price
            leg_delta = abs(structure.legs[0].delta) if structure.legs else 0.5
            ex_prem = max(0.0, entry_premium + (spot_move * direction_sign * leg_delta))
            log.warning(
                "close_position[%s] options: exit_premium not supplied; "
                "using delta-linear estimate (entry=%.4f → est=%.4f, "
                "spot Δ=%.2f, δ=%.3f). Pass exit_premium for correct PnL.",
                pos_id, entry_premium, ex_prem, spot_move, leg_delta,
            )
        # Long options only today (place_order_option always side="buy"), so
        # PnL is unconditionally (exit − entry) × qty. When short-options
        # is added the direction_sign multiplier comes in here.
        raw_pnl = (ex_prem - entry_premium) * qty

    # Bound losses by sized max_risk. Apply max_gain cap only for
    # defined-risk option spreads — futures and naked options have unbounded
    # upside and the previous unconditional cap was silently truncating
    # winners.
    max_risk = pos.sized_trade.max_risk_usd
    bounded = max(-max_risk, raw_pnl)
    max_gain = structure.max_gain
    DEFINED_RISK_STRUCTURES = {
        "bull_call_spread", "bear_put_spread",
        "bull_put_spread", "bear_call_spread",
        "iron_condor", "iron_butterfly",
    }
    if max_gain is not None and structure.structure_type in DEFINED_RISK_STRUCTURES:
        bounded = min(max_gain * qty, bounded)
    estimated_pnl = round(bounded, 2)

    # 1% TDS on the gross sell value for Indian crypto — surfaced for
    # after-tax display, not used in trade decisions. Computed against
    # gross USD value of the closing fill (options: ex_prem × contracts;
    # futures: exit_price × contracts). Skip for paper positions and
    # when fill_type == "settlement" (DEI handles TDS on settlement).
    tds = 0.0
    if not pos.is_paper and fill_type != "settlement":
        gross_close_usd = (
            (locals().get("ex_prem") or 0.0) * qty if not is_futures
            else exit_spot_price * qty
        )
        tds = round(0.01 * gross_close_usd, 2)

    # Record exit in cooldown engine — keyed on (underlying, mode, direction).
    # Same-(underlying, mode, direction) re-entries are blocked for the
    # mode-defined window after this call. Defaults to "swing" for legacy
    # positions persisted before the mode field existed.
    try:
        from app.engines.risk import cooldown
        cooldown.record_exit(
            underlying=pos.underlying,
            mode=getattr(pos, "mode", None) or "swing",
            direction=structure.direction.value,
            exit_ts_ms=int(time.time() * 1000),
        )
    except Exception:
        # Cooldown is advisory — never let a failure here block a close
        pass

    # Phase 5 — close the audit feedback loop. When the position's notes
    # carry a [DERIV-aid=XXXXXXXX] tag (stamped by the per-strategy
    # selector wiring), record the realised PnL on the matching audit
    # row so the operator's seven-day observation feed has full
    # post-trade outcomes per selector decision.
    try:
        import re as _re
        m = _re.search(r"\[DERIV-aid=([0-9a-fA-F]{4,32})\]", pos.notes or "")
        if m:
            from app.services import derivatives_audit as _audit
            # The short-form id stored in notes is the first 8 hex chars
            # of the full uuid; find the matching audit entry in the ring.
            short = m.group(1)
            for r in _audit.list_recent(limit=5000):
                if r["audit_id"].startswith(short):
                    _audit.record_exit(r["audit_id"], exit_pnl=float(estimated_pnl))
                    break
    except Exception:
        pass

    closed = update_position(
        pos_id,
        status=PositionStatus.CLOSED,
        exit_timestamp_ms=int(time.time() * 1000),
        exit_spot_price=exit_spot_price,
        exit_premium=(None if is_futures else round(float(locals().get("ex_prem") or 0.0), 4)),
        realized_pnl_usd=estimated_pnl,
        tds_withheld_usd=(pos.tds_withheld_usd or 0.0) + tds,
        fill_type=fill_type,
        exit_reason=exit_reason,
        settlement_recorded=settlement_recorded,
        notes=notes or pos.notes,
        run_once_state=TradeState.EXITED,
        exit_mode=getattr(pos, 'exit_mode', exit_mode),
        current_red_count=getattr(pos, 'current_red_count', current_red_count),
        exit_threshold=getattr(pos, 'exit_threshold', exit_threshold),
    )
    # Live event emission — no-op unless settings.enable_event_bus configured a
    # bus at startup. Fail-safe: never let event wiring affect a close.
    try:
        from app.services import event_emit
        event_emit.emit_position_closed(pos.underlying, float(estimated_pnl))
    except Exception:
        pass
    return closed


def partial_close_position(
    pos_id: str,
    exit_spot_price: float = 0.0,
    partial_ratio: float = 0.50,
    *,
    exit_premium: Optional[float] = None,
) -> Optional[PaperPosition]:
    """Close `partial_ratio` of the position. Uses the same corrected
    instrument-aware PnL formula as `close_position`: futures = spot-linear
    (no leverage), options = premium delta (with delta-linear fallback +
    warning if `exit_premium` not supplied).
    """
    pos = _positions.get(pos_id)
    if not pos or pos.status != PositionStatus.OPEN:
        return None

    structure      = pos.sized_trade.structure
    direction_sign = 1 if structure.direction.value == "long" else -1
    is_futures     = structure.structure_type == "futures"

    closed_contracts    = max(1, round(pos.sized_trade.contracts * partial_ratio))
    remaining_contracts = max(0, pos.sized_trade.contracts - closed_contracts)
    # Coin quantity being closed = closed lots × lot size (cv defaults to 1.0).
    closed_qty = closed_contracts * pos.sized_trade.contract_value

    if is_futures:
        spot_move = (exit_spot_price - pos.entry_spot_price) if exit_spot_price > 0 else 0.0
        raw_pnl = spot_move * direction_sign * closed_qty
    else:
        entry_premium = (
            pos.entry_premium
            if pos.entry_premium is not None
            else _default_entry_premium(pos.sized_trade) or 0.0
        )
        ex_prem = exit_premium
        if ex_prem is None:
            spot_move = (exit_spot_price - pos.entry_spot_price) if exit_spot_price > 0 else 0.0
            leg_delta = abs(structure.legs[0].delta) if structure.legs else 0.5
            ex_prem = max(0.0, entry_premium + (spot_move * direction_sign * leg_delta))
            log.warning(
                "partial_close_position[%s] options: exit_premium not supplied; "
                "using delta-linear estimate (entry=%.4f → est=%.4f). "
                "Pass exit_premium for correct partial PnL.",
                pos_id, entry_premium, ex_prem,
            )
        raw_pnl = (ex_prem - entry_premium) * closed_qty

    risk_closed = pos.sized_trade.max_risk_usd * partial_ratio
    partial_pnl = max(-risk_closed, raw_pnl)
    DEFINED_RISK_STRUCTURES = {
        "bull_call_spread", "bear_put_spread",
        "bull_put_spread", "bear_call_spread",
        "iron_condor", "iron_butterfly",
    }
    if structure.max_gain is not None and structure.structure_type in DEFINED_RISK_STRUCTURES:
        partial_pnl = min(structure.max_gain * closed_qty, partial_pnl)
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


def clear_positions(mode: str = "") -> int:
    """Delete CLOSED position records only (history cleanup). Open and
    partially-closed positions are kept. `mode` optionally limits to 'paper'
    or 'live'. Returns the number of records removed."""
    m = (mode or "").strip().lower()
    to_remove = [
        pid for pid, p in _positions.items()
        if p.status == PositionStatus.CLOSED
        and (m == "" or (m == "paper" and p.is_paper) or (m == "live" and not p.is_paper))
    ]
    for pid in to_remove:
        del _positions[pid]
        db.remove(pid)
    return len(to_remove)


def open_count() -> int:
    return sum(1 for p in _positions.values() if p.status == PositionStatus.OPEN)


def closed_count() -> int:
    return sum(1 for p in _positions.values() if p.status == PositionStatus.CLOSED)
