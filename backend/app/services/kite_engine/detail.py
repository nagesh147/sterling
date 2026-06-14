"""Compose the click-through detail for a ready signal: trigger context, live
underlying price, and per-leg option quote + market depth + Black-Scholes greeks.

Kite-only; reads live quotes via the user's client. No other-engine imports.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.core.logging import get_logger
from app.engines.triple_supertrend.schemas import (
    DepthLevel, EngineDetailResponse, OptionDetail,
)
from app.services.kite_engine.greeks import black_scholes_greeks, implied_vol
from app.services.kite_engine.scanner import scanner

log = get_logger(__name__)
_IST = timezone(timedelta(hours=5, minutes=30))


def _spot_symbol(underlying: str, option_exchange: str) -> str:
    # SENSEX/BSE names quote on BSE; everything else on NSE. Display name == LTP
    # symbol for indices ("NIFTY 50") and stocks ("RELIANCE") alike.
    return ("BSE:" if option_exchange == "BFO" else "NSE:") + underlying


def _levels(side: list) -> List[DepthLevel]:
    out: List[DepthLevel] = []
    for lv in (side or []):
        try:
            out.append(DepthLevel(price=float(lv.get("price") or 0.0),
                                  quantity=int(lv.get("quantity") or 0),
                                  orders=int(lv.get("orders") or 0)))
        except (TypeError, ValueError):
            continue
    return out


async def build_detail(client, uid: str, token: int) -> Optional[EngineDetailResponse]:
    """Build the detail for the currently-displayed signal row matching ``token``.
    Returns None if no such ready signal is in the latest scan snapshot."""
    row = next((r for r in scanner.snapshot(uid).rows if r.token == token), None)
    if row is None:
        return None

    spot_sym = _spot_symbol(row.underlying, row.exchange)
    spot_now = 0.0
    try:
        d = await client.get_ltp([spot_sym])
        spot_now = float((d.get(spot_sym) or {}).get("last_price") or 0.0)
    except Exception as exc:  # noqa: BLE001
        log.warning("kite-engine detail LTP failed %s: %s", spot_sym, exc)
    spot_ref = spot_now or row.spot

    qsyms = [f"{row.exchange}:{leg.option_symbol}" for leg in row.legs]
    quotes = {}
    if qsyms:
        try:
            quotes = await client.get_quote(qsyms)
        except Exception as exc:  # noqa: BLE001
            log.warning("kite-engine detail quote failed: %s", exc)

    today = datetime.now(_IST).date()
    options: List[OptionDetail] = []
    for leg in row.legs:
        q = quotes.get(f"{row.exchange}:{leg.option_symbol}", {}) or {}
        depth = q.get("depth", {}) or {}
        buy, sell = _levels(depth.get("buy", [])), _levels(depth.get("sell", []))
        bid = buy[0].price if buy else 0.0
        ask = sell[0].price if sell else 0.0
        ltp = float(q.get("last_price") or 0.0)
        iv = float(q.get("implied_volatility") or 0.0) / 100.0
        try:
            dte = (datetime.strptime(leg.expiry, "%Y-%m-%d").date() - today).days
        except (ValueError, TypeError):
            dte = 0
        # Live IV is absent after hours — back it out of the last traded premium so
        # greeks stay meaningful (the user often looks when the market is closed).
        if iv <= 0 and ltp > 0:
            iv = implied_vol(price=ltp, spot=spot_ref, strike=leg.strike,
                             dte_days=dte, option_type=leg.option_type)
        g = black_scholes_greeks(spot=spot_ref, strike=leg.strike, dte_days=dte,
                                 iv=iv, option_type=leg.option_type)
        options.append(OptionDetail(
            moneyness=leg.moneyness, option_type=leg.option_type,
            option_symbol=leg.option_symbol, strike=leg.strike, expiry=leg.expiry,
            lot_size=leg.lot_size, dte=dte, last_price=ltp, bid=bid, ask=ask, iv=iv,
            delta=g.delta, gamma=g.gamma, theta=g.theta, vega=g.vega,
            depth_buy=buy, depth_sell=sell,
        ))

    return EngineDetailResponse(
        underlying=row.underlying, token=row.token, exchange=row.exchange,
        direction=row.direction, regime=row.regime, alignment=row.alignment, option_type=row.option_type,
        triggered_ms=row.timestamp_ms, spot_at_trigger=row.spot, spot_now=spot_now,
        stop_loss=row.stop_loss, options=options,
    )
