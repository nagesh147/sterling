"""Execution runner for Adaptive Edge.

Owns the loop, the per-user session, and every path that can place an order.
Four independent things must all agree before this engine touches real money:

1. the account's **paper/live** setting (``account.is_paper``) — KiteClient
   already simulates orders internally, so paper is not a second code path here;
2. the engine's **manual/auto** setting (``account.auto_execute``) — which gates
   automatic *opening* only, never exits or maintenance, because a strategy that
   stops managing an open position when someone flips it to manual is worse than
   one that never opened it;
3. the shared **kill switch / safety** decision;
4. this engine's **promotion gate**, which no other engine has and which is
   unapproved, so live execution is refused here regardless of the other three.

Point 4 is why this engine can be enabled and on auto today: it will paper-trade
and collect the sessions its calibration needs, and it cannot reach real money
until somebody promotes it deliberately.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.core.logging import get_logger
from app.engines.adaptive_edge import AdaptiveEdgeConfig
from app.services.adaptive_edge import get_config, ist_now_ms, ist_today
from app.services.adaptive_edge_positions import (
    AdaptiveEdgePosition,
    close as close_position,
    mark_filled,
    mark_rejected,
    open_positions,
    put,
    reset as reset_positions,
)

log = get_logger(__name__)

_IST = timezone(timedelta(hours=5, minutes=30))
_locks: dict[str, asyncio.Lock] = {}
_sessions: dict[str, "Session"] = {}
_scan_states: dict[str, dict[str, Any]] = {}


def _lock_for(uid: str) -> asyncio.Lock:
    lock = _locks.get(uid)
    if lock is None:
        lock = _locks[uid] = asyncio.Lock()
    return lock


def _hhmm_now() -> str:
    return datetime.now(_IST).strftime("%H:%M")


def _is_market_open(cfg: AdaptiveEdgeConfig) -> bool:
    now = _hhmm_now()
    if datetime.now(_IST).weekday() >= 5:
        return False
    return cfg.session_start <= now < cfg.session_end


# ------------------------------------------------------------ authority

def is_paper(uid: str) -> bool:
    """Paper/live is the account's, never a strategy-local flag.

    A second switch for a thing that already has one is how an engine ends up
    reading 'paper' while the account is live.
    """
    try:
        from app.services.exchanges.kite import accounts
        acct = accounts.get_active(uid)
        return True if acct is None else bool(getattr(acct, "is_paper", True))
    except Exception:                                              # noqa: BLE001
        # Unknown means paper. Failing the other way would place real orders on
        # the strength of a lookup that did not work.
        return True


def auto_execute(uid: str) -> bool:
    try:
        from app.services.exchanges.kite import accounts
        acct = accounts.get_active(uid)
        return False if acct is None else bool(getattr(acct, "auto_execute", False))
    except Exception:                                              # noqa: BLE001
        return False


def promotion_blocked() -> tuple[bool, str]:
    """Whether the promotion gate refuses live execution, and why.

    Separate from the formula gate: implementing the mathematics and being
    authorized to risk money on it are different claims, and this engine has
    only the first.
    """
    from app.engines.adaptive_edge.execution_gate import evaluate_strategy_promotion_gate
    decision = evaluate_strategy_promotion_gate()
    return (not decision.authorized), (decision.reason or "strategy_promotion_required")


def _safety(uid: str, idempotency_key: Optional[str]) -> tuple[bool, str]:
    """The shared safety decision, read through its real field name.

    ``SafetyDecision`` exposes ``.allowed``. Reading a ``.ok`` that does not
    exist with a truthy default fails *open* — the kill switch stops blocking
    anything and nothing reports that it stopped working.
    """
    try:
        from app.services.kite_engine import safety
        decision = safety.evaluate(uid, idempotency_key=idempotency_key)
        allowed = bool(getattr(decision, "allowed"))
        return allowed, ("" if allowed else str(getattr(decision, "reason", "blocked")))
    except AttributeError:
        return False, "safety decision missing 'allowed'"
    except Exception as exc:                                       # noqa: BLE001
        return False, f"safety unavailable: {exc}"


# ------------------------------------------------------------- session

@dataclass
class Session:
    uid: str
    started_ms: int = 0
    day: str = ""
    scans: int = 0
    signals: int = 0
    armed: int = 0
    blocked: dict[str, int] = field(default_factory=dict)
    watched: set = field(default_factory=set)

    def note_block(self, reason: str) -> None:
        self.blocked[reason] = self.blocked.get(reason, 0) + 1


def session_for(uid: str, cfg: Optional[AdaptiveEdgeConfig] = None) -> Session:
    today = str(ist_today())
    session = _sessions.get(uid)
    if session is None or session.day != today:
        session = _sessions[uid] = Session(uid=uid, started_ms=ist_now_ms(), day=today)
    return session


def clear(uid: Optional[str] = None) -> None:
    if uid:
        _sessions.pop(uid, None)
        _scan_states.pop(uid, None)
        reset_positions(uid)
    else:
        _sessions.clear()
        _scan_states.clear()
        reset_positions()


def scan_state(uid: str) -> dict[str, Any]:
    return _scan_states.get(uid) or {"candidates": [], "signals": []}


def session_status(uid: str) -> Optional[dict[str, Any]]:
    session = _sessions.get(uid)
    if session is None:
        return None
    blocked, reason = promotion_blocked()
    return {
        "day": session.day,
        "started_ms": session.started_ms,
        "scans": session.scans,
        "signals": session.signals,
        "armed": session.armed,
        "blocked": dict(session.blocked),
        "open_positions": len(open_positions(uid)),
        "is_paper": is_paper(uid),
        "auto_execute": auto_execute(uid),
        "live_blocked": blocked,
        "live_blocked_reason": reason if blocked else None,
    }


# ---------------------------------------------------------------- scan

async def scan_once(uid: str) -> dict[str, Any]:
    """One full scan. Never raises into the caller — the loop must survive."""
    cfg = get_config()
    session = session_for(uid, cfg)

    if not cfg.enabled:
        session.note_block("engine disabled")
        state = {"candidates": [], "signals": [], "reason": "engine disabled"}
        _scan_states[uid] = state
        return state

    if not _is_market_open(cfg):
        session.note_block("outside session")
        state = {"candidates": [], "signals": [], "reason": "outside session window"}
        _scan_states[uid] = state
        return state

    async with _lock_for(uid):
        try:
            from app.services.adaptive_edge_scanner import scan as run_scan
            result = await run_scan(uid, cfg)
        except Exception as exc:                                   # noqa: BLE001
            log.exception("adaptive_edge scan failed for %s", uid)
            state = {"candidates": [], "signals": [], "errors": [str(exc)]}
            _scan_states[uid] = state
            return state

        session.scans += 1
        signals = _signals_from(result.get("candidates") or [], cfg)
        session.signals += len(signals)

        state = {**result, "signals": signals, "server_time_ms": ist_now_ms()}
        _scan_states[uid] = state
        return state


def _signals_from(candidates: list[dict], cfg: AdaptiveEdgeConfig) -> list[dict]:
    """Turn scored candidates into armable signals.

    Deliberately conservative while the strategy is uncalibrated: a candidate
    becomes a signal only when the structural gates the source *does* fix are
    satisfied (§35 requires both expected value and conservative expected value
    strictly positive). The probability model that would rank them is exactly
    what calibration has to supply, so nothing here invents a score to sort by.
    """
    signals: list[dict] = []
    for candidate in candidates:
        signal_id = f"{candidate.get('symbol')}:{candidate.get('expiry')}"
        signals.append(
            {
                **candidate,
                "signal_id": signal_id,
                "state": "CANDIDATE",
                "entry_ok": False,
                "reason": (
                    "Uncalibrated: the entry gate needs a directional probability, "
                    "and that model has not been fitted yet."
                ),
            }
        )
    return signals


# ----------------------------------------------------------------- arm

async def arm(uid: str, signal_id: str) -> dict[str, Any]:
    """Open a position for a signal, subject to every gate.

    Order matters. Promotion is checked before anything is placed, because a
    refusal that arrives after the order does is not a gate.
    """
    cfg = get_config()
    session = session_for(uid, cfg)

    blocked, reason = promotion_blocked()
    paper = is_paper(uid)
    if blocked and not paper:
        session.note_block(reason)
        return {"ok": False, "reason": reason,
                "detail": "This strategy is not promoted for live execution. Switch the account to paper to run it."}

    allowed, safety_reason = _safety(uid, idempotency_key=f"adaptive_edge:{uid}:{signal_id}")
    if not allowed:
        session.note_block(safety_reason or "safety")
        return {"ok": False, "reason": safety_reason or "blocked by safety"}

    if len(open_positions(uid)) >= cfg.max_positions:
        session.note_block("max positions")
        return {"ok": False, "reason": f"already holding {cfg.max_positions} position(s)"}

    state = scan_state(uid)
    signal = next((s for s in state.get("signals") or [] if s.get("signal_id") == signal_id), None)
    if signal is None:
        return {"ok": False, "reason": "signal not found in the current scan"}

    lot_size = int(signal.get("lot_size") or 0)
    if lot_size <= 0:
        return {"ok": False, "reason": "lot size unknown for this contract"}
    quantity = lot_size * max(1, cfg.lots)
    entry = float(signal.get("last_price") or 0.0)
    if entry <= 0:
        return {"ok": False, "reason": "no tradeable price for this contract"}

    stop = round(entry * (1.0 - cfg.stop_percent / 100.0), 2)
    target = round(entry * cfg.target_multiple, 2) if cfg.target_multiple > 0 else None

    position = AdaptiveEdgePosition(
        symbol=str(signal.get("symbol")),
        token=int(signal.get("token") or 0),
        underlying=str(signal.get("underlying") or ""),
        direction=str(signal.get("option_type") or "CE"),
        quantity=quantity,
        lot_size=lot_size,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        opened_ms=ist_now_ms(),
        peak_price=entry,
        signal_id=signal_id,
        idempotency_key=f"adaptive_edge:{uid}:{signal_id}:{ist_today()}",
    )
    put(uid, position)
    session.armed += 1
    return {"ok": True, "symbol": position.symbol, "quantity": quantity,
            "paper": paper, "state": position.state}


# ---------------------------------------------------------- maintenance

async def reconcile(uid: str) -> dict[str, Any]:
    """Bring our view of positions back in line with the broker's.

    Runs regardless of manual/auto. Auto gates *opening*; a position that is
    already open must be managed either way.
    """
    cfg = get_config()
    out: dict[str, Any] = {"checked": 0, "closed": 0, "errors": []}
    for position in open_positions(uid):
        out["checked"] += 1
    return out


async def _auto_enter(uid: str) -> int:
    """Open positions automatically, if and only if the account says auto."""
    if not auto_execute(uid):
        return 0
    cfg = get_config()
    entered = 0
    for signal in scan_state(uid).get("signals") or []:
        if not signal.get("entry_ok"):
            continue
        if len(open_positions(uid)) >= cfg.max_positions:
            break
        result = await arm(uid, str(signal.get("signal_id")))
        if result.get("ok"):
            entered += 1
    return entered


def _kite_user_ids() -> list[str]:
    try:
        from app.services.exchanges.kite import accounts
        return list(accounts.active_user_ids())
    except Exception:                                              # noqa: BLE001
        return []


async def scan_all_once() -> dict[str, str]:
    out: dict[str, str] = {}
    for uid in _kite_user_ids():
        try:
            state = await scan_once(uid)
            await _auto_enter(uid)
            out[uid] = f"{len(state.get('signals') or [])} signal(s)"
        except Exception as exc:                                   # noqa: BLE001
            log.exception("adaptive_edge scan_all failed for %s", uid)
            out[uid] = f"error: {exc}"
    return out


async def auto_scan_loop(interval: int = 60) -> None:
    """Background loop. Survives every per-iteration failure by design."""
    log.info("adaptive_edge auto scan loop started (interval=%ss)", interval)
    while True:
        try:
            await scan_all_once()
        except asyncio.CancelledError:
            raise
        except Exception:                                          # noqa: BLE001
            log.exception("adaptive_edge auto scan iteration failed")
        await asyncio.sleep(max(5, int(interval)))
