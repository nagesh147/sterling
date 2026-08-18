"""Production background runner for NIFTY ORB option execution.

Execution ownership remains deliberately split:

    ORB strategy -> signal/plan
    universal Trading Mode -> Paper/Live + Manual/Auto
    Kite execution/protection -> order, idempotency, stops and reconciliation

This module owns only scheduling, verified-session gating, tenant isolation and
single-flight protection. It never introduces a strategy-local execution mode.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.logging import get_logger

log = get_logger(__name__)
IST = ZoneInfo("Asia/Kolkata")
_INTERVAL_S = 5.0
_task: asyncio.Task | None = None
_user_locks: dict[str, asyncio.Lock] = {}


def _lock_for(user_id: str) -> asyncio.Lock:
    lock = _user_locks.get(user_id)
    if lock is None:
        lock = asyncio.Lock()
        _user_locks[user_id] = lock
    return lock


def _is_verified_market_open() -> bool:
    """Fail closed when the NSE calendar does not cover the current year."""
    now = datetime.now(IST)
    try:
        from app.services.navigator.calendar import is_market_open_at
        return bool(is_market_open_at(int(now.timestamp() * 1000)))
    except Exception:
        return False


async def _run_user(user_id: str) -> dict:
    from app.services.nifty_orb_options import execute_auto

    lock = _lock_for(user_id)
    if lock.locked():
        return {"status": "overlap_suppressed"}
    async with lock:
        try:
            return await execute_auto(user_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("NIFTY ORB execution failed for user=%s: %s", user_id, exc)
            return {"status": "error", "message": str(exc)}


async def _tick() -> None:
    from app.services.exchanges.kite import accounts as kite_accounts

    if not _is_verified_market_open():
        return

    kite_accounts.bootstrap()
    # One user can have multiple Kite accounts, but the strategy execution contract
    # is user-scoped and execute_auto resolves that user's active account. Therefore
    # run each user once, never once per account.
    users = {
        account.user_id
        for account in kite_accounts._accounts.values()  # noqa: SLF001
        if account.user_id and account.is_active and account.connected
    }
    if not users:
        return

    results = await asyncio.gather(
        *(_run_user(user_id) for user_id in sorted(users)),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            log.warning("NIFTY ORB tenant tick returned exception: %s", result)
            continue
        status = result.get("status")
        if status in {"executed", "blocked", "error", "expiry_day_blocked", "daily_limit"}:
            log.info("NIFTY ORB auto tick status=%s", status)


async def run_forever() -> None:
    """Run the ORB decision loop until the ASGI lifespan cancels it."""
    while True:
        try:
            await _tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("NIFTY ORB runner failure: %s", exc)
        await asyncio.sleep(_INTERVAL_S)


def start() -> asyncio.Task:
    """Start exactly one process-local runner; safe to call repeatedly."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(run_forever(), name="nifty-orb-options-runner")
    return _task


def stop() -> None:
    """Request runner shutdown; lifespan owns awaiting the task."""
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
    _task = None
