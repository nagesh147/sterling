"""Session runner for OI Wall Flow: scanning, arming, and watching positions out.

The engine decides; this decides *when to ask it* and turns its intents into
orders. Everything with a clock, a socket or a broker in it lives here, which is
what keeps ``app.engines.oi_wall_flow`` replayable.

Two invariants carried over from earlier engines in this codebase:

1. **Tick subscriptions are claimed under this strategy's owner tag.** Releasing
   untagged would pull ticks out from under another engine's protection monitor.
2. **Every exit path takes the position's ``exiting`` claim before sending an
   order.** Premium stop and wall invalidation are two paths to one position;
   without the claim both will flatten it.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.logging import get_logger
from app.engines.oi_wall_flow import (Intent, OIWallFlowConfig, OIWallFlowStrategy,
                                      PositionState, SessionState, STRATEGY_ID,
                                      align_to_tick, q2)
from app.services import oi_wall_flow_positions as positions_store
from app.services.oi_wall_flow import get_config

log = get_logger(__name__)
_IST = timezone(timedelta(hours=5, minutes=30))

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


def _is_market_open(cfg: OIWallFlowConfig) -> bool:
    now = datetime.now(_IST)
    if now.weekday() >= 5:
        return False
    return cfg.session_start <= now.strftime("%H:%M") <= cfg.session_end


async def _client(uid: str):
    from app.services.exchanges.kite import accounts
    acct = accounts.get_active(uid)
    if not acct:
        raise RuntimeError("No active Kite account")
    return await accounts.acquire_client(acct)


def is_paper(uid: str) -> bool:
    """The account's mode — the one authority for Kite paper/live."""
    try:
        from app.services.exchanges.kite import accounts
        acct = accounts.get_active(uid)
        return bool(getattr(acct, "is_paper", True)) if acct else True
    except Exception:                                              # noqa: BLE001
        return True


def auto_execute(uid: str) -> bool:
    """The engine's MANUAL/AUTO switch — likewise read from its own home."""
    try:
        from app.services.kite_engine import state as engine_state
        return bool(getattr(engine_state.get_config(uid), "auto_execute", False))
    except Exception:                                              # noqa: BLE001
        return False


def _safety(uid: str, idempotency_key: Optional[str]) -> tuple[bool, str]:
    try:
        from app.services.live_safety import assert_safe_to_trade
        # check_daily_loss was False here while the breaker read zero for an INR
        # position. daily_loss_state(uid=...) now goes through
        # _account_daily_pnl_inr to state.daily_realized_pnl_strict(uid), which is
        # INR-native and propagates a failed read instead of returning 0, so the
        # gate is armed. uid= is what scopes it to the right account.
        decision = assert_safe_to_trade([], idempotency_key,
                                        check_daily_loss=True, uid=uid)
        return bool(decision.allowed), str(decision.reason or "")
    except Exception as exc:                                       # noqa: BLE001
        log.error("oi_wall_flow: safety check failed closed for %s: %s", uid, exc)
        return False, f"safety check unavailable: {exc}"


async def _confirm_fill(client, order_id: str) -> tuple[str, float]:
    if str(order_id).startswith("PAPER-"):
        return "COMPLETE", 0.0
    try:
        history = await client.get_order_history(order_id)
    except Exception as exc:                                       # noqa: BLE001
        log.warning("oi_wall_flow: order status unavailable for %s: %s", order_id, exc)
        return "UNKNOWN", 0.0
    if not history:
        return "UNKNOWN", 0.0
    last = history[-1] if isinstance(history, list) else history
    status = str((last or {}).get("status") or "").upper()
    try:
        avg = float((last or {}).get("average_price") or 0.0)
    except (TypeError, ValueError):
        avg = 0.0
    return status, avg


class Session:
    def __init__(self, uid: str, cfg: OIWallFlowConfig):
        self.uid = uid
        self.cfg = cfg
        self.strategy = OIWallFlowStrategy(cfg, SessionState(day=_today_str()))
        self.signals: dict[str, object] = {}
        self.subscribed: set[int] = set()
        self.notes: list[dict] = []
        self.last_spot: dict[str, float] = {}
        self.spot_tokens: dict[str, int] = {}

    def note(self, kind: str, message: str) -> None:
        self.notes.append({"kind": kind, "message": message, "at_ms": _now_ms()})
        del self.notes[:-40]


def session_for(uid: str, cfg: Optional[OIWallFlowConfig] = None) -> Session:
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
    cfg = get_config()
    if not cfg.enabled:
        return {"scanned": 0, "armed": 0, "signals": [],
                "message": "this engine is switched off"}
    async with _lock_for(uid):
        session = session_for(uid, cfg)
        from app.services.oi_wall_flow_scanner import last_spot_tokens, last_spots, scan_once as _scan
        signals = await _scan(uid, cfg, session.strategy)
        session.signals = {s.id: s for s in signals}
        session.spot_tokens.update(last_spot_tokens(uid))
        session.last_spot.update(last_spots(uid))
        await _subscribe_watched(uid, session)
        armed = [s for s in signals if s.state == "armed"]
        return {"scanned": len(signals), "armed": len(armed),
                "signals": [s.as_dict() for s in signals]}


def _token_of(instrument) -> int:
    if instrument is None:
        return 0
    tid = getattr(instrument, "instrument_id", "") or ""
    return int(tid) if str(tid).isdigit() else 0


async def _subscribe_watched(uid: str, session: Session) -> None:
    tokens: set[int] = set()
    for s in session.signals.values():
        plan = getattr(s, "plan", None)
        inst = getattr(plan, "instrument", None) if plan is not None else None
        tok = _token_of(inst)
        if tok:
            tokens.add(tok)
    for p in session.strategy.state.positions.values():
        tok = _token_of(p.instrument)
        if tok:
            tokens.add(tok)
    tokens |= {t for t in session.spot_tokens.values() if t}
    new = tokens - session.subscribed
    stale = session.subscribed - tokens
    if new:
        try:
            from app.services.exchanges.kite import ticker_manager
            from app.services.exchanges.kite import constants as K
            await ticker_manager.subscribe(uid, sorted(new), K.MODE_FULL, owner=_OWNER)
            session.subscribed |= new
        except Exception as exc:                                   # noqa: BLE001
            log.warning("oi_wall_flow subscribe failed for %s: %s", uid, exc)
    if stale:
        await _release(uid, session, stale)


async def _release(uid: str, session: Session, tokens: set) -> None:
    if not tokens:
        return
    try:
        from app.services.exchanges.kite import ticker_manager
        await ticker_manager.release(uid, sorted(tokens), owner=_OWNER)
    except Exception as exc:                                       # noqa: BLE001
        log.debug("oi_wall_flow release failed for %s: %s", uid, exc)
    session.subscribed -= tokens


async def release_subscriptions(uid: str) -> None:
    session = _sessions.get(uid)
    if session:
        await _release(uid, session, set(session.subscribed))


# ----------------------------------------------------------------- arming

def _instrument_of(signal):
    plan = getattr(signal, "plan", None)
    return None if plan is None else getattr(plan, "instrument", None)


async def arm(uid: str, signal_id: str) -> dict:
    cfg = get_config()
    if not cfg.enabled:
        return {"ok": False, "message": "this engine is switched off"}
    async with _lock_for(uid):
        session = session_for(uid, cfg)
        signal = session.signals.get(signal_id)
        if signal is None:
            return {"ok": False, "message": f"no signal {signal_id} in this session"}
        blocker = session.strategy.admit(signal, _today_str())
        if blocker:
            return {"ok": False, "message": blocker}
        plan = signal.plan
        if plan is None or plan.quantity <= 0 or plan.entry <= 0:
            return {"ok": False, "message": "signal has no priced entry or size"}
        inst = plan.instrument
        if inst is None or not inst.tradingsymbol:
            return {"ok": False, "message": "signal has no resolved contract"}

        held = positions_store.get(uid, inst.tradingsymbol)
        if held and held.is_open:
            return {"ok": False, "message": f"already holding {inst.tradingsymbol}"}

        idem = f"{STRATEGY_ID}:{uid}:{signal.id}:{_today_str()}"
        ok, why = _safety(uid, idem)
        if not ok:
            session.note("blocked", f"entry refused for {inst.tradingsymbol}: {why}")
            return {"ok": False, "message": why}

        limit = align_to_tick(plan.entry, inst.tick_size)
        client = await _client(uid)
        try:
            res = await client.place_order(
                f"{inst.exchange}:{inst.tradingsymbol}", "buy", float(plan.quantity),
                order_type="limit_order", limit_price=float(limit), tag=STRATEGY_ID[:20])
        except Exception as exc:                                   # noqa: BLE001
            session.note("error", f"entry rejected for {inst.tradingsymbol}: {exc}")
            return {"ok": False, "message": str(exc)}
        order_id = str((res or {}).get("order_id")
                       or ((res or {}).get("data") or {}).get("order_id") or "")
        if not order_id:
            session.note("error",
                         f"{inst.tradingsymbol}: broker returned no order id — "
                         "check positions before retrying")
            return {"ok": False, "message": "broker returned no order id"}

        pos = session.strategy.on_entry(signal, limit, _now_ms(), _today_str())
        pos.order_id = order_id
        pos.stop_mode = cfg.stop_mode
        pos.idempotency_key = idem
        pos.instrument = inst
        positions_store.put(uid, pos)
        session.last_spot[signal.underlying] = float(signal.spot or 0.0) or session.last_spot.get(signal.underlying, 0.0)

        status, avg = await _confirm_fill(client, order_id)
        if status in ("REJECTED", "CANCELLED"):
            positions_store.mark_rejected(uid, inst.tradingsymbol, status)
            session.strategy.state.positions.pop(signal.id, None)
            session.strategy.state.trades_today = max(
                0, session.strategy.state.trades_today - 1)
            session.note("error", f"{inst.tradingsymbol} {status.lower()} at the broker")
            return {"ok": False, "message": f"order {status.lower()}"}

        filled = positions_store.mark_filled(uid, inst.tradingsymbol, avg)
        if filled is not None:
            pos.stop, pos.fill_price, pos.status = filled.stop, filled.fill_price, filled.status

        gtt_id = await _place_protection(uid, client, pos, cfg)
        await _subscribe_watched(uid, session)
        session.note("entry",
                     f"bought {pos.quantity} {inst.tradingsymbol} @ {pos.effective_entry} "
                     f"(stop {pos.stop}{', GTT ' + str(gtt_id) if gtt_id else ''})")
        return {"ok": True, "order_id": order_id, "symbol": inst.tradingsymbol,
                "quantity": pos.quantity, "entry": pos.effective_entry,
                "stop": pos.stop, "gtt_id": gtt_id, "paper": is_paper(uid),
                "status": pos.status}


async def _place_protection(uid: str, client, pos, cfg) -> int:
    if cfg.stop_mode == "monitor" or pos.stop <= 0 or pos.quantity <= 0:
        return 0
    inst = pos.instrument
    symbol = pos.tradingsymbol or (inst.tradingsymbol if inst else "")
    exchange = inst.exchange if inst else "NFO"
    try:
        from app.services.kite_engine.protective_stop import place_stop
        gtt_id = await place_stop(
            client, tradingsymbol=symbol, exchange=exchange, qty=int(pos.quantity),
            trigger_premium=float(pos.stop), last_price=float(pos.effective_entry),
            direction="long", target_premium=float(pos.target or 0.0))
    except Exception as exc:                                       # noqa: BLE001
        gtt_id = None
        log.warning("oi_wall_flow: protective GTT failed for %s: %s", symbol, exc)
    if gtt_id:
        pos.gtt_id = int(gtt_id)
        positions_store.put(uid, pos)
        return int(gtt_id)
    session = _sessions.get(uid)
    if session:
        session.note("warning",
                     f"{symbol}: no broker stop — this process "
                     "is the only thing watching the position")
    return 0


async def adopt(uid: str, symbol: str, quantity: int, entry_price: float) -> dict:
    cfg = get_config()
    async with _lock_for(uid):
        session = session_for(uid, cfg)
        match = next((s for s in session.signals.values()
                      if getattr(getattr(s, "plan", None), "instrument", None)
                      and s.plan.instrument.tradingsymbol == symbol), None)
        if match is None:
            return {"ok": False, "message": f"{symbol} is not a contract this scan knows"}
        inst = match.plan.instrument
        stop = cfg.stop_price(float(entry_price)) or q2(float(entry_price) * 0.6)
        inv = match.plan.underlying_invalidation
        pos = PositionState(
            signal_id=match.id, option_type=inst.option_type, strike=inst.strike,
            entry=q2(entry_price), stop=stop,
            target=cfg.target_price(float(entry_price)) or 0.0,
            quantity=int(quantity),
            lots=max(1, int(quantity) // max(1, inst.lot_size)),
            entered_ms=_now_ms(), entry_day=_today_str(),
            underlying_invalidation=inv, tradingsymbol=symbol,
            target_2=cfg.target_2_price(float(entry_price)),
            instrument=inst, status=positions_store.OPEN,
            fill_price=q2(entry_price), stop_mode=cfg.stop_mode,
        )
        session.strategy.state.positions[match.id] = pos
        positions_store.put(uid, pos)
        gtt_id = await _place_protection(uid, await _client(uid), pos, cfg)
        session.note("adopt", f"adopted {quantity} {symbol} @ {entry_price}, stop {stop}")
        await _subscribe_watched(uid, session)
        return {"ok": True, "symbol": symbol, "stop": stop, "gtt_id": gtt_id}


async def orphan_positions(uid: str, cfg: OIWallFlowConfig) -> list[dict]:
    try:
        client = await _client(uid)
        book = await client.get_positions()
    except Exception as exc:                                       # noqa: BLE001
        log.debug("oi_wall_flow position fetch failed for %s: %s", uid, exc)
        return []
    rows = (book or {}).get("net") or []
    known = {sym for sym, p in positions_store.load(uid).items() if p.is_open}
    out = []
    for r in rows:
        sym = str(r.get("tradingsymbol") or "")
        qty = int(r.get("quantity") or 0)
        if qty <= 0 or str(r.get("exchange")) not in ("NFO", "BFO") or sym in known:
            continue
        if not (sym.endswith("CE") or sym.endswith("PE")):
            continue
        out.append({"symbol": sym, "quantity": qty,
                    "entry_price": q2(float(r.get("average_price") or 0))})
    return out


async def reconcile(uid: str) -> dict:
    cfg = get_config()
    session = session_for(uid, cfg)
    restored = 0
    for sym, pos in positions_store.load(uid).items():
        if pos.is_open:
            session.strategy.state.positions[pos.signal_id or sym] = pos
            restored += 1
    orphans = await orphan_positions(uid, cfg)

    vanished = []
    try:
        client = await _client(uid)
        book = await client.get_positions()
        live = {str(r.get("tradingsymbol")): int(r.get("quantity") or 0)
                for r in ((book or {}).get("net") or [])}
        for key, pos in list(session.strategy.state.positions.items()):
            symbol = pos.tradingsymbol
            if live.get(symbol, 0) <= 0 and not is_paper(uid):
                vanished.append(symbol)
                positions_store.close(uid, symbol, "not at the broker on reconcile")
                session.strategy.state.positions.pop(key, None)
    except Exception as exc:                                       # noqa: BLE001
        log.warning("oi_wall_flow: reconcile could not read the broker for %s: %s", uid, exc)

    if restored or orphans or vanished:
        session.note("reconcile",
                     f"restored {restored}, {len(orphans)} unaccounted, "
                     f"{len(vanished)} gone at the broker")
        log.info("oi_wall_flow reconcile %s: restored=%s orphans=%s vanished=%s",
                 uid, restored, len(orphans), vanished)
    await _subscribe_watched(uid, session)
    return {"restored": restored, "orphans": orphans, "vanished": vanished}


# ------------------------------------------------------------------ ticks

async def on_ticks(uid: str, ticks: list) -> str:
    """Drive open positions from live prices. Returns a short status word."""
    session = _sessions.get(uid)
    if not session or not session.strategy.state.positions:
        return "idle"
    cfg = session.cfg
    by_token = {int(t.get("instrument_token") or 0): t for t in ticks or []}
    today = _today_str()
    client = None

    # Keep last-known spots so wall invalidation has a number even when the
    # option tick arrives without a matching underlying tick in the same batch.
    for name, tok in session.spot_tokens.items():
        tick = by_token.get(tok)
        if tick:
            try:
                px = float(tick.get("last_price") or 0)
            except (TypeError, ValueError):
                px = 0.0
            if px > 0:
                session.last_spot[name] = px

    acted = "watching"
    for key, pos in list(session.strategy.state.positions.items()):
        tid = _token_of(pos.instrument)
        tick = by_token.get(tid)
        if not tick:
            continue
        try:
            ltp = float(tick.get("last_price") or 0)
        except (TypeError, ValueError):
            ltp = 0.0
        if ltp <= 0:
            continue
        underlying = (pos.signal_id or "").split(":")[0]
        spot = session.last_spot.get(underlying) or 0.0
        decision = session.strategy.on_price(pos, ltp, spot)
        if decision.intent is not Intent.EXIT or not decision.exit_position:
            continue

        client = client or await _client(uid)
        await _cancel_protection(uid, client, pos)
        tick_size = pos.instrument.tick_size if pos.instrument else 0.05
        price = align_to_tick(ltp, tick_size)
        symbol = pos.tradingsymbol
        exchange = pos.instrument.exchange if pos.instrument else "NFO"
        try:
            res = await client.place_order(
                f"{exchange}:{symbol}", "sell",
                float(pos.quantity), order_type="limit_order", limit_price=float(price),
                tag=f"{STRATEGY_ID[:14]}-ex")
            oid = str((res or {}).get("order_id") or "")
        except Exception as exc:                                   # noqa: BLE001
            pos.exiting = False
            await _place_protection(uid, client, pos, cfg)
            session.note("error", f"exit rejected for {symbol}: {exc}")
            continue
        if not oid:
            pos.exiting = False
            await _place_protection(uid, client, pos, cfg)
            session.note("error", f"exit for {symbol} returned no order id")
            continue

        pnl = session.strategy.on_exit(pos, price, today, key)
        positions_store.close(uid, symbol, decision.exit_reason)
        session.note("exit", f"sold {pos.quantity} {symbol} @ {price} "
                             f"({decision.exit_reason}), Rs {pnl:,.0f}")
        acted = "exited"
    if not session.strategy.state.positions:
        await _subscribe_watched(uid, session)
    return acted


async def _cancel_protection(uid: str, client, pos) -> None:
    if not pos.gtt_id:
        return
    try:
        from app.services.kite_engine.protective_stop import cancel_stop
        await cancel_stop(client, int(pos.gtt_id))
    except Exception as exc:                                       # noqa: BLE001
        log.warning("oi_wall_flow: could not cancel the broker stop for %s: %s",
                    pos.tradingsymbol, exc)
    pos.gtt_id = 0
    positions_store.put(uid, pos)


# ----------------------------------------------------------------- status

def scan_state(uid: str) -> dict:
    from app.services.oi_wall_flow_scanner import scan_stats
    return scan_stats(uid)


def session_status(uid: str) -> Optional[dict]:
    session = _sessions.get(uid)
    if not session:
        return None
    st = session.strategy.state
    positions = []
    for key, p in st.positions.items():
        positions.append({
            "symbol": p.tradingsymbol, "signal_id": p.signal_id,
            "entry": p.entry, "stop": p.stop, "target": p.target,
            "target_2": p.target_2, "quantity": p.quantity, "lots": p.lots,
            "entered_ms": p.entered_ms, "entry_day": p.entry_day,
            "exiting": p.exiting, "high_water": p.high_water,
            "underlying_invalidation": p.underlying_invalidation,
            "option_type": p.option_type, "strike": p.strike,
            "status": p.status, "order_id": p.order_id,
            "fill_price": p.fill_price, "effective_entry": p.effective_entry,
            "gtt_id": p.gtt_id, "stop_mode": p.stop_mode,
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
    cfg = get_config()
    out: dict[str, str] = {}
    if not cfg.enabled:
        return {"*": "disabled"}
    if not _is_market_open(cfg):
        return {"*": "outside session"}
    for uid in _kite_user_ids():
        try:
            res = await scan_once(uid)
            note = f"{res['armed']} armed of {res['scanned']}"
            if res["armed"] and auto_execute(uid):
                taken = await _auto_enter(uid)
                note += f", auto-entered {taken}"
            out[uid] = note
        except Exception as exc:                                   # noqa: BLE001
            out[uid] = f"error: {exc}"
            log.warning("oi_wall_flow scan failed for %s: %s", uid, exc)
    return out


async def _auto_enter(uid: str) -> int:
    session = _sessions.get(uid)
    if not session:
        return 0
    armed = sorted(
        (s for s in session.signals.values() if s.state == "armed" and s.plan),
        key=lambda s: -abs(s.bias.score),
    )
    taken = 0
    for signal in armed:
        result = await arm(uid, signal.id)
        if result.get("ok"):
            taken += 1
        elif "limit" in str(result.get("message", "")) or "cap" in str(result.get("message", "")):
            break
    return taken


async def reconcile_all() -> dict[str, dict]:
    out = {}
    for uid in _kite_user_ids():
        try:
            out[uid] = await reconcile(uid)
        except Exception as exc:                                   # noqa: BLE001
            log.warning("oi_wall_flow reconcile failed for %s: %s", uid, exc)
    return out


async def auto_scan_loop(interval: int = 300) -> None:
    log.info("oi_wall_flow auto-scan loop started (every %ss)", interval)
    try:
        await reconcile_all()
    except Exception as exc:                                       # noqa: BLE001
        log.warning("oi_wall_flow startup reconcile failed: %s", exc)
    while True:
        try:
            cfg = get_config()
            if cfg.enabled and _is_market_open(cfg):
                await scan_all_once()
            interval = max(60, int(cfg.scan_interval_seconds or interval))
        except asyncio.CancelledError:
            raise
        except Exception as exc:                                   # noqa: BLE001
            log.warning("oi_wall_flow auto-scan cycle failed: %s", exc)
        await asyncio.sleep(interval)
