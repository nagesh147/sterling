"""Session runner for Gamma Move: scanning, arming, and watching positions out.

The engine decides; this decides *when to ask it* and turns its intents into
orders. Everything with a clock, a socket or a broker in it lives here, which is
what keeps ``app.engines.gamma_move`` replayable.

Two invariants carried over from earlier engines in this codebase, both easy to
lose and both expensive:

1. **Tick subscriptions are claimed under this strategy's owner tag.** Releasing
   untagged would pull ticks out from under another engine's protection monitor.
2. **Every exit path takes the position's ``exiting`` claim before sending an
   order.** Stop, trail, target, time stop and session end are five paths to one
   position; without the claim two of them will both flatten it.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.gamma_move import (GammaMoveConfig, GammaMoveStrategy, GammaSignal,
                                    Intent, PositionState, SessionState, STRATEGY_ID,
                                    align_to_tick, exit_order_price, q2)
from app.services.gamma_move import get_config, ist_today

log = get_logger(__name__)
_IST = timezone(timedelta(hours=5, minutes=30))

#: Claims this strategy's tick subscriptions so they can be released without
#: disturbing anyone else's.
_OWNER = STRATEGY_ID

_sessions: dict[str, "Session"] = {}
_locks: dict[str, asyncio.Lock] = {}


def _lock_for(uid: str) -> asyncio.Lock:
    lock = _locks.get(uid)
    if lock is None:
        lock = _locks[uid] = asyncio.Lock()
    return lock


def _now_ms() -> int:
    return int(datetime.now(_IST).timestamp() * 1000)


def _today_str() -> str:
    return datetime.now(_IST).strftime("%Y-%m-%d")


def _is_market_open(cfg: GammaMoveConfig) -> bool:
    now = datetime.now(_IST)
    if now.weekday() >= 5:
        return False
    return cfg.session_start <= now.strftime("%H:%M") <= cfg.session_end


# ----------------------------------------------------------------- broker

class BrokerPort:
    """The narrow broker surface this runner needs."""

    async def place(self, *, exchange: str, tradingsymbol: str, side: str,
                    quantity: int, limit_price: float,
                    tag: str) -> tuple[Optional[str], Optional[str]]:
        raise NotImplementedError


class PaperBrokerPort(BrokerPort):
    """Fills at the limit price and records nothing with the broker.

    Paper is the default and is not a stub: it is the only mode this strategy is
    permitted to run in until the live gate passes, so it must behave.
    """

    def __init__(self) -> None:
        self.orders: list[dict] = []

    async def place(self, *, exchange, tradingsymbol, side, quantity, limit_price, tag):
        oid = f"paper-{len(self.orders) + 1}-{tradingsymbol}"
        self.orders.append({"order_id": oid, "symbol": f"{exchange}:{tradingsymbol}",
                            "side": side, "quantity": quantity,
                            "limit_price": q2(limit_price), "tag": tag})
        return oid, None


class KiteBrokerPort(BrokerPort):
    def __init__(self, client: Any) -> None:
        self._client = client

    async def place(self, *, exchange, tradingsymbol, side, quantity, limit_price, tag):
        try:
            res = await self._client.place_order(
                f"{exchange}:{tradingsymbol}", side, float(quantity),
                order_type="limit_order", limit_price=float(limit_price), tag=tag)
        except Exception as exc:                                   # noqa: BLE001
            log.error("gamma_move order failed (%s %s): %s", side, tradingsymbol, exc)
            return None, str(exc)
        oid = None
        if isinstance(res, dict):
            oid = res.get("order_id") or (res.get("data") or {}).get("order_id")
        return (str(oid) if oid else None), None


async def _broker_for(uid: str, cfg: GammaMoveConfig) -> BrokerPort:
    if cfg.execution_mode != "live":
        return PaperBrokerPort()
    from app.services.exchanges.kite import accounts
    acct = accounts.get_active(uid)
    if not acct:
        raise RuntimeError("No active Kite account")
    return KiteBrokerPort(await accounts.acquire_client(acct))


# ---------------------------------------------------------------- session

class Session:
    def __init__(self, uid: str, cfg: GammaMoveConfig):
        self.uid = uid
        self.cfg = cfg
        self.strategy = GammaMoveStrategy(cfg, SessionState(day=_today_str()))
        self.signals: dict[str, GammaSignal] = {}
        self.subscribed: set[int] = set()
        self.notes: list[dict] = []

    def note(self, kind: str, message: str) -> None:
        self.notes.append({"kind": kind, "message": message, "at_ms": _now_ms()})
        del self.notes[:-40]


def session_for(uid: str, cfg: Optional[GammaMoveConfig] = None) -> Session:
    cfg = cfg or get_config()
    s = _sessions.get(uid)
    if s is None or s.strategy.state.day != _today_str():
        s = _sessions[uid] = Session(uid, cfg)
    s.cfg = cfg
    s.strategy.cfg = cfg
    s.strategy.state.roll(_today_str())
    return s


def clear(uid: Optional[str] = None) -> None:
    if uid:
        _sessions.pop(uid, None)
    else:
        _sessions.clear()


# -------------------------------------------------------------- scanning

async def scan_once(uid: str) -> dict:
    """One full A->B->C pass. Returns a summary for the API."""
    cfg = get_config()
    async with _lock_for(uid):
        session = session_for(uid, cfg)
        from app.services.gamma_move_scanner import scan_once as _scan
        signals = await _scan(uid, cfg, session.strategy)
        session.signals = {s.id: s for s in signals}
        await _subscribe_watched(uid, session)
        armed = [s for s in signals if s.state == "armed"]
        return {"scanned": len(signals), "armed": len(armed),
                "signals": [s.as_dict() for s in signals]}


async def _subscribe_watched(uid: str, session: Session) -> None:
    """Full-mode ticks for everything being watched or held.

    MODE_FULL, not quote: the open-interest fields this strategy exists to read
    are only present in full packets.
    """
    tokens = {int(s.candidate.instrument.instrument_id)
              for s in session.signals.values()
              if s.candidate.instrument.instrument_id.isdigit()}
    tokens |= {int(p.instrument.instrument_id)
               for p in session.strategy.state.positions.values()
               if p.instrument.instrument_id.isdigit()}
    new = tokens - session.subscribed
    stale = session.subscribed - tokens
    if new:
        try:
            from app.services.exchanges.kite import ticker_manager
            from app.services.exchanges.kite import constants as K
            await ticker_manager.subscribe(uid, sorted(new), K.MODE_FULL, owner=_OWNER)
            session.subscribed |= new
        except Exception as exc:                                   # noqa: BLE001
            log.warning("gamma_move subscribe failed for %s: %s", uid, exc)
    if stale:
        await _release(uid, session, stale)


async def _release(uid: str, session: Session, tokens: set) -> None:
    if not tokens:
        return
    try:
        from app.services.exchanges.kite import ticker_manager
        await ticker_manager.release(uid, sorted(tokens), owner=_OWNER)
    except Exception as exc:                                       # noqa: BLE001
        log.debug("gamma_move release failed for %s: %s", uid, exc)
    session.subscribed -= tokens


async def release_subscriptions(uid: str) -> None:
    session = _sessions.get(uid)
    if session:
        await _release(uid, session, set(session.subscribed))


# ----------------------------------------------------------------- arming

async def arm(uid: str, signal_id: str) -> dict:
    """Enter one armed signal. Refusals are returned, never raised silently."""
    cfg = get_config()
    async with _lock_for(uid):
        session = session_for(uid, cfg)
        signal = session.signals.get(signal_id)
        if signal is None:
            return {"ok": False, "message": f"no signal {signal_id} in this session"}
        blocker = session.strategy.admit(signal, _today_str())
        if blocker:
            return {"ok": False, "message": blocker}
        if signal.entry is None or signal.quantity is None or signal.quantity <= 0:
            return {"ok": False, "message": "signal has no priced entry or size"}

        inst = signal.candidate.instrument
        limit = align_to_tick(signal.entry, inst.tick_size)
        broker = await _broker_for(uid, cfg)
        oid, err = await broker.place(exchange=inst.exchange,
                                      tradingsymbol=inst.tradingsymbol, side="BUY",
                                      quantity=int(signal.quantity), limit_price=limit,
                                      tag=STRATEGY_ID[:20])
        if err or not oid:
            session.note("error", f"entry rejected for {inst.tradingsymbol}: {err}")
            return {"ok": False, "message": err or "broker returned no order id"}

        pos = session.strategy.on_entry(signal, limit, _now_ms(), _today_str())
        session.note("entry", f"bought {signal.quantity} {inst.tradingsymbol} @ {limit}")
        await _subscribe_watched(uid, session)
        return {"ok": True, "order_id": oid, "symbol": inst.tradingsymbol,
                "quantity": signal.quantity, "entry": limit, "stop": pos.stop}


async def adopt(uid: str, symbol: str, quantity: int, entry_price: float) -> dict:
    """Take responsibility for a position this engine did not open."""
    cfg = get_config()
    async with _lock_for(uid):
        session = session_for(uid, cfg)
        match = next((s for s in session.signals.values()
                      if s.candidate.instrument.tradingsymbol == symbol), None)
        if match is None:
            return {"ok": False, "message": f"{symbol} is not a contract this scan knows"}
        inst = match.candidate.instrument
        stop = q2(float(entry_price) * (1 - cfg.stop_percent / 100.0))
        pos = PositionState(signal_id=match.id, instrument=inst, entry=q2(entry_price),
                            stop=stop, quantity=int(quantity),
                            lots=max(1, int(quantity) // max(1, inst.lot_size)),
                            entered_ms=_now_ms(), entry_day=_today_str())
        session.strategy.state.positions[symbol] = pos
        session.note("adopt", f"adopted {quantity} {symbol} @ {entry_price}, stop {stop}")
        await _subscribe_watched(uid, session)
        return {"ok": True, "symbol": symbol, "stop": stop}


async def orphan_positions(uid: str, cfg: GammaMoveConfig) -> list[dict]:
    """Open NFO option longs this engine is not accounting for.

    A position nothing is watching is the most dangerous state this strategy can
    be in, because arming again would double the exposure.
    """
    if cfg.execution_mode != "live":
        return []
    try:
        from app.services.exchanges.kite import accounts
        acct = accounts.get_active(uid)
        if not acct:
            return []
        client = await accounts.acquire_client(acct)
        positions = await client.get_positions()
    except Exception as exc:                                       # noqa: BLE001
        log.debug("gamma_move position fetch failed for %s: %s", uid, exc)
        return []
    rows = (positions or {}).get("net") or []
    session = _sessions.get(uid)
    known = set(session.strategy.state.positions) if session else set()
    out = []
    for r in rows:
        sym = str(r.get("tradingsymbol") or "")
        qty = int(r.get("quantity") or 0)
        if qty <= 0 or str(r.get("exchange")) != "NFO" or sym in known:
            continue
        if not (sym.endswith("CE") or sym.endswith("PE")):
            continue
        out.append({"symbol": sym, "quantity": qty,
                    "entry_price": q2(float(r.get("average_price") or 0))})
    return out


# ------------------------------------------------------------------ ticks

async def on_ticks(uid: str, ticks: list, broker: Optional[BrokerPort] = None) -> str:
    """Drive open positions from live prices. Returns a short status word."""
    session = _sessions.get(uid)
    if not session or not session.strategy.state.positions:
        return "idle"
    cfg = session.cfg
    by_token = {int(t.get("instrument_token") or 0): t for t in ticks or []}
    today = _today_str()
    session_over = not _is_market_open(cfg)
    broker = broker or await _broker_for(uid, cfg)

    acted = "watching"
    for pos in list(session.strategy.state.positions.values()):
        tid = int(pos.instrument.instrument_id) if pos.instrument.instrument_id.isdigit() else 0
        tick = by_token.get(tid)
        if not tick:
            continue
        ltp = float(tick.get("last_price") or 0)
        if ltp <= 0:
            continue
        decision = session.strategy.on_price(pos, ltp, _now_ms(), today,
                                             session_over=session_over)
        if decision.intent is not Intent.EXIT or not decision.exit_position:
            continue
        price = exit_order_price(ltp, pos.instrument.tick_size)
        oid, err = await broker.place(exchange=pos.instrument.exchange,
                                      tradingsymbol=pos.instrument.tradingsymbol,
                                      side="SELL", quantity=pos.quantity,
                                      limit_price=price, tag=f"{STRATEGY_ID[:14]}-exit")
        if err or not oid:
            # The claim is released so a later tick can retry; leaving it set
            # would strand the position with nothing able to close it.
            pos.exiting = False
            session.note("error", f"exit rejected for {pos.instrument.tradingsymbol}: {err}")
            continue
        pnl = session.strategy.on_exit(pos, price, today)
        session.note("exit", f"sold {pos.quantity} {pos.instrument.tradingsymbol} @ {price} "
                             f"({decision.exit_reason}), Rs {pnl:,.0f}")
        acted = "exited"
    if not session.strategy.state.positions:
        await _subscribe_watched(uid, session)
    return acted


# ----------------------------------------------------------------- status

def scan_state(uid: str) -> dict:
    from app.services.gamma_move_scanner import scan_stats
    return scan_stats(uid)


def session_status(uid: str) -> Optional[dict]:
    session = _sessions.get(uid)
    if not session:
        return None
    st = session.strategy.state
    positions = []
    for sym, p in st.positions.items():
        positions.append({
            "symbol": sym, "signal_id": p.signal_id, "entry": p.entry, "stop": p.stop,
            "trail": p.trail, "target": p.target, "quantity": p.quantity,
            "lots": p.lots, "entered_ms": p.entered_ms, "entry_day": p.entry_day,
            "sessions_held": p.sessions_held, "exiting": p.exiting,
            "high_water": p.high_water,
        })
    return {
        "day": st.day, "phase": st.phase.value, "halt_reason": st.halt_reason,
        "trades_today": st.trades_today,
        "candidates": [s.as_dict() for s in session.signals.values()],
        "positions": positions,
        "record": st.record.as_dict(),
        "subscribed": sorted(session.subscribed),
        "notes": session.notes[-10:],
    }


# ------------------------------------------------------------ auto-scanning

def _kite_user_ids() -> list[str]:
    try:
        from app.services.exchanges.kite import accounts
        accounts.bootstrap()
        return sorted({a.user_id for a in accounts.all_accounts() if a.is_active})
    except Exception:                                              # noqa: BLE001
        return []


async def scan_all_once() -> dict[str, str]:
    """One scan for every account with the strategy enabled."""
    cfg = get_config()
    out: dict[str, str] = {}
    if not cfg.enabled:
        return {"*": "disabled"}
    if not _is_market_open(cfg):
        return {"*": "outside session"}
    for uid in _kite_user_ids():
        try:
            res = await scan_once(uid)
            out[uid] = f"{res['armed']} armed of {res['scanned']}"
        except Exception as exc:                                   # noqa: BLE001
            out[uid] = f"error: {exc}"
            log.warning("gamma_move scan failed for %s: %s", uid, exc)
    return out


async def auto_scan_loop(interval: int = 300) -> None:
    """Background scanner. Never dies on one bad cycle."""
    log.info("gamma_move auto-scan loop started (every %ss)", interval)
    while True:
        try:
            cfg = get_config()
            if cfg.enabled and _is_market_open(cfg):
                await scan_all_once()
            interval = max(60, int(cfg.scan_interval_seconds or interval))
        except asyncio.CancelledError:
            raise
        except Exception as exc:                                   # noqa: BLE001
            log.warning("gamma_move auto-scan cycle failed: %s", exc)
        await asyncio.sleep(interval)
