"""
Session-level endpoints.
GET /session/export  — full session data JSON bundle
DELETE /session/reset — clear all in-memory session state (keep SQLite)
"""
import time
from fastapi import APIRouter

from app.services import paper_store, eval_history, arrow_store, alert_store, pnl_history
from app.services.exchanges import instrument_registry as registry

router = APIRouter(prefix="/session", tags=["session"])


@router.get("/export")
async def export_session():
    """
    Download the full session state as a JSON bundle.
    Covers: positions, alerts, arrows, eval history, P&L history per position.
    """
    all_syms = [i.underlying for i in registry.list_instruments()]
    positions = paper_store.list_positions()

    return {
        "export_version": "1",
        "export_timestamp_ms": int(time.time() * 1000),
        "positions": [p.model_dump() for p in positions],
        "alerts": [a.model_dump() for a in alert_store.list_alerts()],
        "arrows": [e.model_dump() for e in arrow_store.get_all()],
        "eval_history": {
            sym: eval_history.get_history(sym)
            for sym in all_syms
            if eval_history.get_history(sym)
        },
        "pnl_history": {
            p.id: [s.model_dump() for s in pnl_history.get_history(p.id)]
            for p in positions
            if pnl_history.get_history(p.id)
        },
        "summary": {
            "positions_open": sum(1 for p in positions if p.status.value == "open"),
            "positions_closed": sum(1 for p in positions if p.status.value == "closed"),
            "alerts_active": alert_store.active_count(),
            "alerts_triggered": alert_store.triggered_count(),
            "total_arrows": len(arrow_store.get_all()),
        },
    }


@router.delete("/reset", status_code=204)
async def reset_session():
    """
    Clear all in-memory session state.
    Paper positions in SQLite are NOT affected — only in-memory eval/arrow/alert history.
    """
    eval_history.clear()
    arrow_store.clear()
    alert_store.clear()
    pnl_history.clear()
