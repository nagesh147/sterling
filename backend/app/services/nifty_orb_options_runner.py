"""Background runner for the NIFTY ORB strategy.

The runner deliberately consumes the universal Kite engine execution state instead of
creating another Paper/Live or Manual/Auto switch. It is a peer signal engine to
SuperTrend and invokes the strategy service only when the universal auto-execute gate
is already enabled.
"""
from __future__ import annotations

import asyncio

from app.core.logging import get_logger

log = get_logger(__name__)
_INTERVAL_S = 60
_task: asyncio.Task | None = None


async def _tick() -> None:
    from app.services.exchanges.kite import accounts as kite_accounts
    from app.services.kite_engine.market_hours import is_market_open
    from app.services.nifty_orb_options import execute_auto

    if not is_market_open():
        return

    # The account store is the authoritative multi-tenant source. We intentionally
    # iterate only active, connected accounts; inactive accounts must never generate
    # exchange traffic or execute a strategy.
    for account in list(kite_accounts._accounts.values()):  # noqa: SLF001
        if not account.is_active or not account.connected:
            continue
        try:
            result = await execute_auto(account.user_id)
            if result.get("status") not in {"advisory", "no_trade_plan", "position_exists", "duplicate_signal", "disabled"}:
                log.info("NIFTY ORB auto tick user=%s status=%s", account.user_id, result.get("status"))
        except Exception as exc:  # noqa: BLE001
            # One tenant must never terminate the runner for every other tenant.
            log.exception("NIFTY ORB auto tick failed for user=%s: %s", account.user_id, exc)


async def run_forever() -> None:
    while True:
        try:
            await _tick()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("NIFTY ORB runner failure: %s", exc)
        await asyncio.sleep(_INTERVAL_S)


def start() -> asyncio.Task:
    """Start exactly one process-local ORB runner."""
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(run_forever(), name="nifty-orb-options-runner")
    return _task
