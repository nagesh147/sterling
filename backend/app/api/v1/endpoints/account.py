"""
Account data endpoints — uses the currently active exchange adapter.
All read-only in paper mode; real data when is_paper=False with valid API creds.

GET /account/info           — active exchange config info
GET /account/summary        — portfolio snapshot for active exchange
GET /account/balances       — wallet balances
GET /account/positions      — open positions
GET /account/orders         — open orders
GET /account/fills          — recent fills/trades
GET /account/fills/export   — fills as CSV download
GET /account/positions/export — positions as CSV download
"""
import csv
import io
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.schemas.account import (
    AssetBalance, AccountPosition, AccountOrder, AccountFill,
    PortfolioSnapshot, AccountSummaryResponse,
)
from app.services import exchange_account_store as store
from app.services.exchanges.adapter_factory import create_account_adapter

router = APIRouter(prefix="/account", tags=["account"])


def _get_active_adapter():
    cfg = store.get_active()
    if not cfg:
        raise HTTPException(status_code=409, detail="No active exchange configured")
    return cfg, create_account_adapter(cfg)


@router.get("/info")
async def account_info():
    cfg = store.get_active()
    if not cfg:
        return {"active": False, "message": "No exchange configured"}
    return {
        "active": True,
        "exchange_id": cfg.id,
        "exchange_name": cfg.name,
        "display_name": cfg.display_name,
        "is_paper": cfg.is_paper,
        "api_key_hint": cfg.api_key_hint(),
        "timestamp_ms": int(time.time() * 1000),
    }


@router.get("/summary", response_model=AccountSummaryResponse)
async def account_summary() -> AccountSummaryResponse:
    now_ms = int(time.time() * 1000)
    cfg = store.get_active()
    if not cfg:
        raise HTTPException(status_code=409, detail="No active exchange configured")

    adapter = create_account_adapter(cfg)
    try:
        connected = await adapter.test_connection()
        portfolio = await adapter.get_portfolio_snapshot() if connected else None
    except Exception as exc:
        return AccountSummaryResponse(
            exchange_id=cfg.id, exchange_name=cfg.name,
            display_name=cfg.display_name, is_paper=cfg.is_paper,
            is_connected=False, error=str(exc), timestamp_ms=now_ms,
        )
    finally:
        await adapter.close()

    return AccountSummaryResponse(
        exchange_id=cfg.id, exchange_name=cfg.name,
        display_name=cfg.display_name, is_paper=cfg.is_paper,
        is_connected=connected, portfolio=portfolio, timestamp_ms=now_ms,
    )


@router.get("/balances")
async def get_balances():
    cfg, adapter = _get_active_adapter()
    try:
        balances = await adapter.get_balances()
        return {
            "exchange": cfg.display_name,
            "is_paper": cfg.is_paper,
            "balances": [b.model_dump() for b in balances],
            "count": len(balances),
            "timestamp_ms": int(time.time() * 1000),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await adapter.close()


@router.get("/positions")
async def get_positions(underlying: str = Query(default="")):
    cfg, adapter = _get_active_adapter()
    try:
        positions = await adapter.get_positions()
        if underlying.strip():
            positions = [p for p in positions if p.underlying.upper() == underlying.upper()]
        return {
            "exchange": cfg.display_name,
            "is_paper": cfg.is_paper,
            "positions": [p.model_dump() for p in positions],
            "count": len(positions),
            "timestamp_ms": int(time.time() * 1000),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await adapter.close()


@router.get("/orders")
async def get_open_orders(underlying: str = Query(default="")):
    cfg, adapter = _get_active_adapter()
    try:
        orders = await adapter.get_open_orders(underlying=underlying.strip() or None)
        return {
            "exchange": cfg.display_name,
            "is_paper": cfg.is_paper,
            "orders": [o.model_dump() for o in orders],
            "count": len(orders),
            "timestamp_ms": int(time.time() * 1000),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await adapter.close()


@router.get("/fills")
async def get_fills(limit: int = Query(default=50, ge=1, le=200)):
    cfg, adapter = _get_active_adapter()
    try:
        fills = await adapter.get_fills(limit=limit)
        return {
            "exchange": cfg.display_name,
            "is_paper": cfg.is_paper,
            "fills": [f.model_dump() for f in fills],
            "count": len(fills),
            "timestamp_ms": int(time.time() * 1000),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await adapter.close()


# ─── CSV exports ─────────────────────────────────────────────────────────────

def _ts_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


@router.get("/fills/export")
async def export_fills_csv(limit: int = Query(default=200, ge=1, le=500)):
    cfg, adapter = _get_active_adapter()
    try:
        fills = await adapter.get_fills(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await adapter.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["fill_id", "order_id", "symbol", "side", "size",
                "price", "fee", "fee_asset", "pnl", "created_at"])
    for f in fills:
        w.writerow([f.fill_id, f.order_id, f.symbol, f.side, f.size,
                    f.price, f.fee, f.fee_asset, f.pnl, _ts_iso(f.created_at_ms)])

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sterling_fills_{cfg.name}.csv"'},
    )


@router.get("/positions/export")
async def export_positions_csv():
    cfg, adapter = _get_active_adapter()
    try:
        positions = await adapter.get_positions()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    finally:
        await adapter.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["symbol", "underlying", "side", "size", "entry_price",
                "mark_price", "unrealized_pnl", "realized_pnl", "margin",
                "position_type", "leverage"])
    for p in positions:
        w.writerow([p.symbol, p.underlying, p.side, p.size, p.entry_price,
                    p.mark_price, p.unrealized_pnl, p.realized_pnl, p.margin,
                    p.position_type, p.leverage or ""])

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="sterling_positions_{cfg.name}.csv"'},
    )
