"""
Session statistics — aggregated counts from all in-memory stores.
GET /stats/session
"""
import time
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

from app.services import arrow_store, alert_store, paper_store, eval_history
from app.services.exchanges import instrument_registry as registry

router = APIRouter(prefix="/stats", tags=["stats"])


class SessionStats(BaseModel):
    green_arrows: int
    red_arrows: int
    total_arrows: int
    alerts_active: int
    alerts_triggered: int
    alerts_dismissed: int
    run_once_total: int
    confirmed_long_setups: int
    confirmed_short_setups: int
    paper_positions_open: int
    paper_positions_closed: int
    underlyings_with_arrows: List[str]
    timestamp_ms: int


@router.get("/session", response_model=SessionStats)
async def session_stats() -> SessionStats:
    now_ms = int(time.time() * 1000)

    all_arrows = arrow_store.get_all()
    green_count = sum(1 for a in all_arrows if a.arrow_type == "green")
    red_count = sum(1 for a in all_arrows if a.arrow_type == "red")
    underlyings_with_arrows = list({a.underlying for a in all_arrows})

    all_alerts = alert_store.list_alerts()
    active_count = sum(1 for a in all_alerts if a.status.value == "active")
    triggered_count = sum(1 for a in all_alerts if a.status.value == "triggered")
    dismissed_count = sum(1 for a in all_alerts if a.status.value == "dismissed")

    all_syms = [i.underlying for i in registry.list_instruments()]
    run_once_total = sum(len(eval_history.get_history(sym)) for sym in all_syms)

    # Count confirmed setups from eval history
    confirmed_long = confirmed_short = 0
    for sym in all_syms:
        for entry in eval_history.get_history(sym):
            state = entry.get("state", "")
            direction = entry.get("direction", "")
            if state == "CONFIRMED_SETUP_ACTIVE":
                if direction == "long":
                    confirmed_long += 1
                elif direction == "short":
                    confirmed_short += 1

    positions = paper_store.list_positions()

    return SessionStats(
        green_arrows=green_count,
        red_arrows=red_count,
        total_arrows=len(all_arrows),
        alerts_active=active_count,
        alerts_triggered=triggered_count,
        alerts_dismissed=dismissed_count,
        run_once_total=run_once_total,
        confirmed_long_setups=confirmed_long,
        confirmed_short_setups=confirmed_short,
        paper_positions_open=sum(1 for p in positions if p.status.value == "open"),
        paper_positions_closed=sum(1 for p in positions if p.status.value == "closed"),
        underlyings_with_arrows=sorted(underlyings_with_arrows),
        timestamp_ms=now_ms,
    )
