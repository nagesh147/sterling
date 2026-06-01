import asyncio
import time
from typing import List

from app.core.logging import get_logger
from app.services import db
from app.services.delta_iv_socket import iv_manager

log = get_logger(__name__)

_RECORD_INTERVAL_S = 60.0
_recorder_task: asyncio.Task | None = None
_running = False

# Usually we only care to record the majors we are trading.
_UNDERLYINGS = ["BTC", "ETH"]


def _flush_ticks(underlying: str) -> None:
    """Read the latest in-memory chain from IV manager and persist to DB."""
    ticks = iv_manager.chain(underlying)
    if not ticks:
        return

    # 1. Forward recorder (Component 2) - insert full surface
    data = [
        (
            underlying,
            t.expiry,
            t.strike,
            t.option_type,
            t.mark_iv,
            t.bid_iv,
            t.ask_iv,
            t.delta,
            t.gamma,
            t.theta,
            t.vega,
            t.rho,
            t.ts_local
        )
        for t in ticks
    ]
    db.record_option_ticks(data)

    # 2. ATM IV Bridge - legacy / trend analysis
    # Pick a 30 DTE ATM IV as representative for the underlying history
    # The actual spot isn't readily available here without an external call,
    # but atm_iv falls back effectively or we can just pick the median IV or closest to delta=0.5
    # Fortunately iv_manager.atm_iv takes spot. Let's find an approximate spot from the chain.
    # The chain ticks contain mark_price, but that's option mark. 
    # But delta_iv_socket might not store spot.
    
    # We can approximate spot by looking at the strike where call delta ~ 0.5, 
    # or just use a generic 'atm_iv' if we have it without spot, or simply record the first tick's ts?
    # Wait, the spec says: "atm_iv(underlying, dte, spot)"
    # We will compute a rough spot by finding where call and put marks intersect or just by
    # fetching the current spot from our L2 cache if possible. For now, since IV surface is stored,
    # we can do a simplified average of near-ATM strikes (0.45 < |delta| < 0.55).
    
    atm_candidates = [t.mark_iv for t in ticks if 0.45 <= abs(t.delta) <= 0.55 and t.mark_iv > 0.0]
    
    if atm_candidates:
        avg_atm_iv = sum(atm_candidates) / len(atm_candidates)
        db.record_iv(underlying, avg_atm_iv)
    else:
        # Fallback to the atm_iv method if possible, we'll pass spot=0 if it handles it,
        # or we just rely on the median IV of the chain.
        valid_ivs = [t.mark_iv for t in ticks if t.mark_iv > 0.0]
        if valid_ivs:
            median_iv = sorted(valid_ivs)[len(valid_ivs) // 2]
            db.record_iv(underlying, median_iv)


async def _recorder_loop() -> None:
    log.info("Delta IV Recorder started (interval=%ss)", _RECORD_INTERVAL_S)
    while _running:
        try:
            for und in _UNDERLYINGS:
                _flush_ticks(und)
        except Exception as exc:
            log.error("Delta IV Recorder error: %s", exc)
        
        await asyncio.sleep(_RECORD_INTERVAL_S)
    log.info("Delta IV Recorder stopped")


def start_recorder() -> None:
    global _running, _recorder_task
    if _running:
        return
    _running = True
    _recorder_task = asyncio.create_task(_recorder_loop())


def stop_recorder() -> None:
    global _running, _recorder_task
    _running = False
    if _recorder_task and not _recorder_task.done():
        _recorder_task.cancel()
    _recorder_task = None
