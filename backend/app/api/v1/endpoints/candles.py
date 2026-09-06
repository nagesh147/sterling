"""
Generic OHLC candles for any underlying.

Thirteen mounted Kite components read this through the `useCandles` hook —
KiteTicker, InstrumentPane, KiteDashboard, AstroPane and every chart — so it is
load-bearing for the whole charting surface.

It previously went through `app.services.adapter_manager`, the multi-exchange
adapter layer. That layer was removed with the crypto product surface (there is
no `app.state.adapter` any more either), so this now resolves the instrument
from the registry and fetches through the user's Kite client, the same path
`/kite/historical` uses.
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.exchanges import instrument_registry as registry
from app.services.exchanges.kite import accounts as kite_accounts
from app.schemas.instruments import InstrumentMeta
from app.core.auth import UserContext, get_current_user

router = APIRouter(prefix="/candles", tags=["candles"])

#: Resolutions `KiteClient.get_candles` maps through `K.RESOLUTION_MAP`.
_VALID_TFS = {"1m", "5m", "15m", "1H", "4H", "D"}


def _ad_hoc(sym: str, token: int) -> InstrumentMeta:
    """A registry miss is normal: charts open on tradingsymbols the 2-name
    registry does not carry. Only the zerodha token is needed to fetch."""
    return InstrumentMeta(
        underlying=sym, quote_currency="INR", contract_multiplier=1.0,
        tick_size=0.05, strike_step=0.0, has_options=False,
        exchange="zerodha", exchange_currency="INR", perp_symbol="",
        index_name=sym, zerodha_token=token, zerodha_index_symbol=sym,
        description=f"Ad-hoc instrument {sym}",
    )


@router.get("/{underlying}")
async def get_candles(
    underlying: str,
    tf: str = Query(default="15m"),
    limit: int = Query(default=1825, ge=1, le=1825),
    token: int = Query(default=0, description="Zerodha instrument token, when the symbol is not in the registry"),
    user: UserContext = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    if tf not in _VALID_TFS:
        raise HTTPException(400, f"Invalid tf: {tf!r}. Valid: {sorted(_VALID_TFS)}")

    sym = underlying.upper()

    acct = kite_accounts.get_active(user.user_id)
    if not acct or not acct.connected:
        raise HTTPException(503, "Kite session unavailable — log in first")
    client = await kite_accounts.acquire_client(acct)

    # Callers pass three different shapes for the same thing, so resolve in the
    # same order the original did:
    #   1. a registry key            — "NIFTY"
    #   2. a zerodha index symbol    — "NSE:NIFTY 50"   (what the charts send)
    #   3. any exchange:tradingsymbol — "NSE:RELIANCE", resolved via the
    #      instruments dump
    inst = registry.get_instrument(sym)
    if inst is None:
        inst = next((c for c in registry.list_instruments()
                     if getattr(c, "zerodha_index_symbol", None) == underlying), None)
    if inst is None and token:
        inst = _ad_hoc(sym, token)
    if inst is None:
        exchange, tradingsymbol = underlying.split(":", 1) if ":" in underlying else ("NSE", underlying)
        try:
            resolved = await client.resolve_token(tradingsymbol, exchange)
        except Exception:  # noqa: BLE001
            resolved = 0
        if resolved:
            inst = _ad_hoc(sym, resolved)
    if inst is None:
        raise HTTPException(404, f"Unknown underlying: {underlying}")
    try:
        candles = await client.get_candles(inst, tf, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Candle fetch failed: {exc}") from exc

    return [
        {
            "time": int(c.timestamp_ms / 1000),
            "open": c.open, "high": c.high, "low": c.low,
            "close": c.close, "volume": c.volume,
        }
        for c in candles
    ]
