"""
Live order execution endpoint.
Places real orders on Delta Exchange India when active exchange config has credentials.
Falls back to paper position creation when credentials are absent.
"""
import json
import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.services.exchanges import instrument_registry as registry
from app.services import paper_store
from app.core.logging import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/trading", tags=["trading"])


class LiveOrderRequest(BaseModel):
    underlying: str
    direction: str           # "long" or "short"
    instrument_type: str     # "futures" or "options"
    size: float = 1.0        # number of contracts
    leverage: float = 5.0    # for futures
    order_type: str = "market"  # "market" or "limit"
    limit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    # For options
    option_symbol: Optional[str] = None  # e.g. "C-BTC-80000-050626"
    option_premium: Optional[float] = None
    notes: str = ""


class LiveOrderResponse(BaseModel):
    mode: str              # "live" or "paper"
    order_id: Optional[str] = None
    paper_position_id: Optional[str] = None
    symbol: str
    side: str
    size: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    leverage: Optional[float] = None
    status: str
    message: str
    timestamp_ms: int


@router.post("/place-order", response_model=LiveOrderResponse)
async def place_live_order(body: LiveOrderRequest, request: Request) -> LiveOrderResponse:
    """
    Place a live order on Delta Exchange India (or paper if not configured).
    Automatically sets bracket SL/TP when provided.
    """
    from app.services import adapter_manager as _adm
    from app.services import exchange_account_store

    sym = body.underlying.upper()
    inst = registry.get_instrument(sym)
    if not inst:
        raise HTTPException(status_code=404, detail=f"Unknown underlying: {sym}")

    side = "buy" if body.direction == "long" else "sell"
    now_ms = int(time.time() * 1000)

    # Check if Delta Exchange India is active with credentials
    active = exchange_account_store.get_active()
    has_live_creds = (
        active is not None
        and active.name in ("delta_india", "delta")
        and bool(active.api_key)
        and bool(active.api_secret)
        and not active.is_paper
    )

    if has_live_creds:
        # ── LIVE ORDER ────────────────────────────────────────────────────
        try:
            # Use a dedicated Delta India adapter with live credentials.
            # _adm.get_adapter() is the market-data adapter (Deribit/etc.) and
            # does not have place_order — we always need DeltaIndiaAdapter here.
            from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter
            adapter = DeltaIndiaAdapter(
                api_key=active.api_key,
                api_secret=active.api_secret,
                is_paper=False,
            )
            if not hasattr(adapter, "place_order"):
                raise RuntimeError("Active adapter does not support live order placement")

            if body.instrument_type == "options" and body.option_symbol:
                order = await adapter.place_order_option(
                    option_symbol=body.option_symbol,
                    side=side,
                    size=body.size,
                    order_type="market_order" if body.order_type == "market" else "limit_order",
                    limit_price=body.limit_price,
                    stop_loss=body.stop_loss,
                    take_profit=body.take_profit,
                )
                delta_symbol = body.option_symbol
            else:
                delta_symbol = inst.delta_perp_symbol or f"{sym}USDT"
                order = await adapter.place_order(
                    symbol=delta_symbol,
                    side=side,
                    size=body.size,
                    order_type="market_order" if body.order_type == "market" else "limit_order",
                    limit_price=body.limit_price,
                    leverage=body.leverage,
                    stop_loss=body.stop_loss,
                    take_profit=body.take_profit,
                )

            order_id = str(order.get("id") or order.get("order_id") or "")
            entry_price = float(order.get("average_fill_price") or order.get("limit_price") or 0.0)

            # Also create a paper tracking entry for P&L monitoring
            _create_paper_tracking(body, sym, entry_price, order_id)

            # Telegram alert
            _send_order_telegram(body, sym, side, entry_price, order_id, "LIVE")

            return LiveOrderResponse(
                mode="live", order_id=order_id,
                symbol=delta_symbol, side=side, size=body.size,
                entry_price=entry_price or None,
                stop_loss=body.stop_loss, take_profit=body.take_profit,
                leverage=body.leverage if body.instrument_type == "futures" else None,
                status="filled" if not body.limit_price else "pending",
                message=f"Live {side.upper()} order placed on Delta Exchange India",
                timestamp_ms=now_ms,
            )

        except Exception as exc:
            log.error("Live order failed: %s", exc)
            raise HTTPException(status_code=502, detail=f"Order failed: {exc}")

    else:
        # ── PAPER ORDER ───────────────────────────────────────────────────
        adapter = _adm.get_adapter() or request.app.state.adapter
        try:
            entry_price = float(await adapter.get_index_price(inst))
        except Exception:
            entry_price = 0.0

        pos_id = _create_paper_tracking(body, sym, entry_price)
        _send_order_telegram(body, sym, side, entry_price, pos_id, "PAPER")

        return LiveOrderResponse(
            mode="paper", paper_position_id=pos_id,
            symbol=inst.delta_perp_symbol or f"{sym}USDT",
            side=side, size=body.size,
            entry_price=entry_price,
            stop_loss=body.stop_loss, take_profit=body.take_profit,
            leverage=body.leverage if body.instrument_type == "futures" else None,
            status="open",
            message=f"Paper {side.upper()} position created (no live credentials configured)",
            timestamp_ms=now_ms,
        )


def _create_paper_tracking(body: LiveOrderRequest, sym: str, entry_price: float, order_id: str = "") -> str:
    """Create a tracking entry in paper_store for P&L monitoring."""
    try:
        from app.schemas.execution import Direction as ExecDir
        from app.schemas.execution import TradeStructure, SizedTrade, CandidateContract
        from app.engines.directional.sizing_engine import size_trade
        from app.schemas.risk import RiskParams

        is_live_order = bool(order_id)
        direction = ExecDir.LONG if body.direction == "long" else ExecDir.SHORT
        leg = CandidateContract(
            instrument_name=body.option_symbol or f"{sym}-PERP",
            strike=entry_price, expiry_date="", option_type=body.instrument_type,
            mark_price=entry_price, mark_iv=None,
            delta=1.0 if body.direction == "long" else -1.0, dte=0,
        )
        structure = TradeStructure(
            structure_type=body.instrument_type,
            direction=direction, legs=[leg],
            net_premium=entry_price, max_loss=entry_price * 0.03,
            max_gain=None, risk_reward=2.0,
            setup_reason=body.notes or f"{'LIVE' if is_live_order else 'PAPER'} {body.direction.upper()} {body.instrument_type}",
            score=0.0, score_breakdown={},
        )
        risk = RiskParams()
        sized = size_trade(structure, risk, leverage=int(body.leverage))
        pos = paper_store.add_position(
            underlying=sym, sized_trade=sized,
            entry_spot_price=entry_price,
            notes=f"{'[LIVE]' if is_live_order else '[PAPER]'} {body.notes} order_id={order_id}",
            is_paper=not is_live_order,   # live orders are tracked as is_paper=False
        )
        return pos.id
    except Exception as exc:
        log.warning("Paper tracking creation failed: %s", exc)
        return ""


def _send_order_telegram(body: LiveOrderRequest, sym: str, side: str, entry: float, ref_id: str, mode: str):
    """Send Telegram notification for order placement."""
    try:
        from app.services.notifications import telegram as _tg
        import asyncio as _aio
        dir_emoji = "🟢 BUY" if side == "buy" else "🔴 SELL"
        sl_str = f"${body.stop_loss:,.2f}" if body.stop_loss else "—"
        tp_str = f"${body.take_profit:,.2f}" if body.take_profit else "—"
        lev_str = f"{int(body.leverage)}×" if body.instrument_type == "futures" else "options"
        msg = (
            f"<b>{'[LIVE]' if mode=='LIVE' else '[PAPER]'} ORDER PLACED</b>\n"
            f"<b>{sym}</b>  {dir_emoji}  {body.instrument_type.upper()}\n"
            f"Entry: <b>${entry:,.2f}</b>  ·  {lev_str}\n"
            f"Stop Loss: <b>{sl_str}</b>\n"
            f"Take Profit: <b>{tp_str}</b>\n"
            f"Ref: {ref_id}"
        )
        _aio.create_task(_tg.send(msg))
    except Exception:
        pass


@router.get("/test-credentials")
async def test_credentials(request: Request) -> dict:
    """
    Verify live credentials against both Delta Exchange endpoints (global + India).
    Calls GET /v2/wallet/balances (read-only, no order placed).
    """
    from app.services import exchange_account_store
    from app.services.exchanges.adapters.delta_india import DeltaIndiaAdapter

    active = exchange_account_store.get_active()
    if not active or not active.api_key or not active.api_secret:
        return {"ok": False, "reason": "No credentials configured", "hint": "Enter API key and secret in Settings."}
    if active.api_key.startswith("DUMMY") or active.api_secret.startswith("DUMMY"):
        return {"ok": False, "reason": "Placeholder credentials detected", "hint": "Replace the default DUMMY key/secret with real Delta Exchange credentials."}

    errors = {}
    for label, base_url in [("Global (delta.exchange)", "https://api.delta.exchange"),
                             ("India (india.delta.exchange)", "https://api.india.delta.exchange")]:
        adapter = DeltaIndiaAdapter(api_key=active.api_key, api_secret=active.api_secret,
                                    is_paper=False, base_url=base_url)
        try:
            data = await adapter._auth_get("/v2/wallet/balances")
            balances = (data.get("result") or [])
            usd = next((b for b in balances if b.get("asset_symbol") in ("USDT", "USD")), None)
            avail = usd.get("available_balance", 0) if usd else 0
            return {
                "ok": True,
                "account": f"{label}",
                "balance": f"${float(avail):,.2f} available",
                "message": f"Connected via {label} — ${float(avail):,.2f} margin available",
                "base_url": base_url,
            }
        except Exception as exc:
            errors[label] = str(exc)

    # Both failed — give a consolidated error
    global_err = errors.get("Global (delta.exchange)", "")
    hint = ""
    if "invalid_api_key" in global_err or "invalid_api_key" in errors.get("India (india.delta.exchange)", ""):
        hint = "API key not recognised on either platform. Regenerate from delta.exchange → Settings → API Keys and re-enter in Sterling."
    elif "403" in global_err or "Forbidden" in global_err:
        hint = "API key exists but lacks Order Management permission. Enable it in Delta Exchange API settings."
    else:
        hint = "Check that the key was generated on delta.exchange (not testnet) and has Read + Order Management permissions."
    return {"ok": False, "reason": f"Global: {global_err}", "hint": hint}


@router.get("/order-status/{order_id}")
async def get_order_status(order_id: str, request: Request) -> dict:
    """Check status of a live order."""
    from app.services import adapter_manager as _adm
    adapter = _adm.get_adapter() or request.app.state.adapter
    try:
        orders = await adapter.get_open_orders()
        for o in orders:
            if o.order_id == order_id:
                return {"order_id": order_id, "status": o.status, "filled": o.filled_size, "size": o.size}
        return {"order_id": order_id, "status": "filled_or_cancelled"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.delete("/cancel-order/{order_id}")
async def cancel_order(order_id: str, product_id: int, request: Request) -> dict:
    """Cancel a live open order."""
    from app.services import adapter_manager as _adm
    adapter = _adm.get_adapter() or request.app.state.adapter
    try:
        result = await adapter.cancel_order(order_id, product_id)
        return {"cancelled": True, "order_id": order_id, "result": result}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
