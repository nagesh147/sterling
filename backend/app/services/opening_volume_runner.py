"""Background scan/execution loop for enabled Opening Leader tenants."""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger

log = get_logger(__name__)
_INTERVAL_SECONDS = 300
_task: asyncio.Task | None = None
_locks: dict[str, asyncio.Lock] = {}


def _market_open() -> bool:
    from datetime import datetime

    from app.engines.opening_volume_leaders import IST

    try:
        from app.services.navigator.calendar import is_market_open_at

        return bool(is_market_open_at(int(datetime.now(IST).timestamp() * 1000)))
    except Exception:
        return False


async def run_user(uid: str) -> dict:
    from app.services.opening_volume_execution import execute_opening_scan, get_config
    from app.services.opening_volume_leaders import scan_kite_leaders
    from app.services.kite_engine import state as engine_state

    lock = _locks.setdefault(uid, asyncio.Lock())
    if lock.locked():
        return {"status": "overlap_suppressed"}
    async with lock:
        config = get_config(uid)
        if not config.enabled:
            return {"status": "disabled"}
        if not engine_state.get_config(uid).auto_execute:
            return {"status": "manual"}
        if not _market_open():
            return {"status": "market_closed"}
        scan = await scan_kite_leaders(uid)
        if not _market_open():
            return {"status": "market_closed"}
        return await execute_opening_scan(uid, scan=scan, config=config)


async def tick() -> None:
    from app.services.exchanges.kite import accounts
    from app.services.opening_volume_execution import get_config

    if not _market_open():
        return
    accounts.bootstrap()
    users = {
        account.user_id
        for account in accounts._accounts.values()
        if account.user_id and account.is_active and account.connected
    }
    enabled = [uid for uid in sorted(users) if get_config(uid).enabled]
    results = await asyncio.gather(*(run_user(uid) for uid in enabled), return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            log.error("Opening Leader tenant tick failed: %s", result)


async def run_forever() -> None:
    while True:
        try:
            await tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("Opening Leader runner failed: %s", exc)
        await asyncio.sleep(_INTERVAL_SECONDS)


def start() -> asyncio.Task:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(run_forever(), name="opening-volume-leaders-runner")
    return _task


def stop() -> None:
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
    _task = None
