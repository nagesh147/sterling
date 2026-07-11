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
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.schemas.account import AccountSummaryResponse
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


@router.get("/summary")
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
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await adapter.close()


# ─── CSV exports ─────────────────────────────────────────────────────────────

def _ts_iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


@router.get("/fills/summary")
async def get_fills_summary(limit: int = Query(default=200, ge=1, le=500)):
    """
    Aggregate fee summary across recent fills.
    Returns total commissions paid, GST, liquidation fees, VIP/DETO discounts,
    fill-type breakdown, and average effective rate.
    """
    from app.services.fees import summarise_fills
    cfg, adapter = _get_active_adapter()
    try:
        fills = await adapter.get_fills(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await adapter.close()

    from app.services.fees import FeeBreakdown
    breakdowns = []
    for f in fills:
        breakdowns.append(FeeBreakdown(
            notional_usd     = f.notional_usd,
            gross_commission = f.gross_commission,
            vip_discount     = f.vip_discount,
            deto_discount    = f.deto_discount,
            tfc_used         = f.tfc_used,
            net_commission   = f.fee,
            liquidation_fee  = f.liquidation_fee,
            gst_amount       = f.gst_amount,
            total_with_gst   = f.total_with_gst,
            total_cost       = f.total_cost,
            effective_rate   = f.effective_rate,
            fill_type        = f.fill_type,
            role             = f.role,
            settling_asset   = f.settling_asset,
        ))

    s = summarise_fills(breakdowns)
    return {
        "exchange":              cfg.display_name,
        "is_paper":              cfg.is_paper,
        "fills_analysed":        s.total_fills,
        "fill_type_breakdown":   {
            "normal":            s.normal_fills,
            "liquidation":       s.liquidation_fills,
            "adl":               s.adl_fills,
            "settlement":        s.settlement_fills,
            "otc":               s.otc_fills,
        },
        "role_breakdown":        {"taker": s.taker_fills, "maker": s.maker_fills},
        "total_notional":        s.total_notional,
        "total_gross_commission":s.total_gross_commission,
        "total_vip_discount":    s.total_vip_discount,
        "total_deto_discount":   s.total_deto_discount,
        "total_tfc_used":        s.total_tfc_used,
        "total_net_commission":  s.total_net_commission,
        "total_liquidation_fee": s.total_liquidation_fee,
        "total_gst":             s.total_gst,
        "total_cost_with_gst":   s.total_cost_with_gst,
        "total_rebates_earned":  s.total_rebates,
        "avg_effective_rate":    s.avg_effective_rate,
        "gst_note":              "GST (18%) is not in the Delta API. Applied as post-processing.",
        "timestamp_ms":          int(time.time() * 1000),
    }


@router.get("/trading-preferences")
async def get_trading_preferences():
    """
    GET /v2/users/trading_preferences — VIP level, discount factor, DETO setting.
    Used to apply correct fee discounts to pre-trade estimates.
    """
    cfg, adapter = _get_active_adapter()
    try:
        if hasattr(adapter, "get_trading_preferences"):
            prefs = await adapter.get_trading_preferences()
        else:
            prefs = {}
        return {
            "exchange":          cfg.display_name,
            "is_paper":          cfg.is_paper,
            "vip_level":         prefs.get("vip_level", 0),
            "vip_discount_factor": float(prefs.get("vip_discount_factor") or 0.0),
            "deto_for_commission": bool(prefs.get("deto_for_commission", False)),
            "volume_30d":        float(prefs.get("volume_30d") or 0.0),
            "taker_rate":        0.0005,
            "maker_rate":        0.0002,
            "gst_rate":          0.18,
            "timestamp_ms":      int(time.time() * 1000),
        }
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await adapter.close()


@router.get("/fills/export")
async def export_fills_csv(limit: int = Query(default=200, ge=1, le=500)):
    cfg, adapter = _get_active_adapter()
    try:
        fills = await adapter.get_fills(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        await adapter.close()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "fill_id", "order_id", "symbol", "side", "size", "price",
        "fill_type", "role",
        "notional_usd", "gross_commission", "net_commission",
        "vip_discount", "deto_discount", "tfc_used",
        "liquidation_fee", "gst_amount", "total_with_gst", "total_cost",
        "effective_rate", "settling_asset", "pnl", "created_at",
    ])
    for f in fills:
        w.writerow([
            f.fill_id, f.order_id, f.symbol, f.side, f.size, f.price,
            f.fill_type, f.role,
            f.notional_usd, f.gross_commission, f.fee,
            f.vip_discount, f.deto_discount, f.tfc_used,
            f.liquidation_fee, f.gst_amount, f.total_with_gst, f.total_cost,
            f.effective_rate, f.settling_asset, f.pnl, _ts_iso(f.created_at_ms),
        ])

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
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
