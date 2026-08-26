"""Operator-facing simulation for Gamma Move.

Everything it produces is stamped ``simulation`` so the board can never render
replayed numbers as live ones -- the same rule ATM Premium Imbalance follows.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.core.logging import get_logger

log = get_logger(__name__)
_IST = timezone(timedelta(hours=5, minutes=30))
_state: dict[str, dict] = {}
_tasks: dict[str, asyncio.Task] = {}


def _now_ms() -> int:
    return int(datetime.now(_IST).timestamp() * 1000)


def state(uid: str) -> Optional[dict]:
    """The current or most recent simulation, or None if there has never been one."""
    return _state.get(uid)


async def _run(uid: str, symbols: list[str], days: int) -> None:
    from app.services.gamma_move_replay import replay_symbol
    from app.engines.gamma_move import summarise
    results: list[dict] = []
    try:
        for i, sym in enumerate(symbols, 1):
            _state[uid] = {**_state[uid], "progress": f"{i}/{len(symbols)}",
                           "current": sym}
            try:
                results.append(await replay_symbol(uid, sym, days=days))
            except Exception as exc:                               # noqa: BLE001
                results.append({"tradingsymbol": sym, "error": str(exc)})
        traded = [r for r in results if r.get("events")]
        _state[uid] = {
            "simulation": True, "status": "done", "finished_ms": _now_ms(),
            "symbols": symbols, "days": days, "results": results,
            "summary": summarise(traded),
            "caveat": ("simulated fills at the bar close, no spread and no brokerage; "
                       "these are not live numbers"),
        }
    except asyncio.CancelledError:
        _state[uid] = {**_state.get(uid, {}), "status": "stopped",
                       "finished_ms": _now_ms()}
        raise
    except Exception as exc:                                       # noqa: BLE001
        log.warning("gamma_move simulation failed for %s: %s", uid, exc)
        _state[uid] = {**_state.get(uid, {}), "status": "error", "error": str(exc),
                       "finished_ms": _now_ms()}


async def start(uid: str, symbols: list[str], days: int = 60) -> dict:
    if _tasks.get(uid) and not _tasks[uid].done():
        return {"ok": False, "message": "a simulation is already running"}
    if not symbols:
        return {"ok": False, "message": "no contracts to simulate"}
    _state[uid] = {"simulation": True, "status": "running", "started_ms": _now_ms(),
                   "symbols": symbols, "days": days, "progress": f"0/{len(symbols)}"}
    _tasks[uid] = asyncio.create_task(_run(uid, symbols, days))
    return {"ok": True, "symbols": len(symbols)}


async def stop(uid: str) -> dict:
    task = _tasks.get(uid)
    if not task or task.done():
        return {"ok": False, "message": "no simulation running"}
    task.cancel()
    return {"ok": True}
