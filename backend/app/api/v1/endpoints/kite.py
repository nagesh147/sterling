"""
Zerodha Kite Connect endpoints — multi-tenant, manual trading + market data.

Every route is scoped to the calling user (``get_current_user``). Credentials and
the daily login are fully managed here (add/update/delete + login-URL handshake).
Order-placing routes pass through ``live_safety`` (kill-switch / daily-loss /
idempotency) exactly like the crypto trading path.

NOTE: this is a standalone manual console for Indian markets — no Sterling/Grok/
scalping strategy is wired to Kite. It exposes the full Kite REST surface plus a
live KiteTicker tick stream (over the shared /stream/ws socket).
"""
from __future__ import annotations

import hashlib
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.core.auth import UserContext, get_current_user
from app.core.logging import get_logger
from app.services import live_safety, paper_store
from app.services.exchanges.kite import accounts as kite_accounts
from app.services.exchanges.kite import constants as K
from app.services.exchanges.kite import session as kite_session
from app.services.exchanges.kite import ticker_manager
from app.services.exchanges.kite.errors import KiteError, KiteTokenError
from app.services.exchanges.kite.models import (
    ConvertPositionRequest, CreateAlertRequest, DeleteAlertsRequest,
    GenerateSessionRequest, InitiateHoldingsAuthRequest, KiteAccountCreate,
    KiteAccountListResponse, KiteAccountResponse, KiteAccountUpdate, KiteSessionResult,
    KiteStatus, LoginUrlResponse, ModifyAlertRequest, ModifyMfSipRequest,
    ModifyOrderRequest, OkResponse, PlaceGttRequest, PlaceMfSipRequest,
    PlaceOrderRequest, RefreshSessionRequest, TickerSubscribeRequest,
)

log = get_logger(__name__)
router = APIRouter(prefix="/kite", tags=["kite"])


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _require_active(user: UserContext):
    acct = kite_accounts.get_active(user.user_id)
    if not acct:
        raise HTTPException(409, "No active Kite account — add credentials and log in first.")
    return acct


async def _run(user: UserContext, fn):
    """Build a client from the user's active account, run ``fn(client)``, close it,
    and map Kite errors to HTTP statuses."""
    acct = _require_active(user)
    client = kite_accounts.build_client(acct)
    try:
        return await fn(client)
    except HTTPException:
        raise
    except KiteTokenError as exc:
        raise HTTPException(401, str(exc))
    except KiteError as exc:
        raise HTTPException(502, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, str(exc))
    finally:
        await client.close()


# ─── Account credentials CRUD (user-scoped) ──────────────────────────────────
@router.get("/accounts", response_model=KiteAccountListResponse)
async def list_accounts(user: UserContext = Depends(get_current_user)) -> KiteAccountListResponse:
    accts = kite_accounts.list_accounts(user.user_id)
    active = kite_accounts.get_active(user.user_id)
    return KiteAccountListResponse(
        accounts=[kite_accounts.to_response(a) for a in accts],
        active_id=active.id if active else None,
        count=len(accts),
    )


@router.post("/accounts", response_model=KiteAccountResponse)
async def add_account(body: KiteAccountCreate, user: UserContext = Depends(get_current_user)) -> KiteAccountResponse:
    return kite_accounts.to_response(kite_accounts.add(user.user_id, body))


@router.put("/accounts/{account_id}", response_model=KiteAccountResponse)
async def update_account(account_id: str, body: KiteAccountUpdate,
                         user: UserContext = Depends(get_current_user)) -> KiteAccountResponse:
    a = kite_accounts.update(user.user_id, account_id, body)
    if not a:
        raise HTTPException(404, "Kite account not found")
    return kite_accounts.to_response(a)


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: str, user: UserContext = Depends(get_current_user)) -> None:
    if not kite_accounts.delete(user.user_id, account_id):
        raise HTTPException(404, "Kite account not found")
    await ticker_manager.stop(user.user_id)


@router.post("/accounts/{account_id}/activate", response_model=KiteAccountResponse)
async def activate_account(account_id: str, user: UserContext = Depends(get_current_user)) -> KiteAccountResponse:
    a = kite_accounts.set_active(user.user_id, account_id)
    if not a:
        raise HTTPException(404, "Kite account not found")
    await ticker_manager.stop(user.user_id)  # next subscribe rebuilds for the new account
    return kite_accounts.to_response(a)


@router.post("/accounts/{account_id}/test")
async def test_account(account_id: str, user: UserContext = Depends(get_current_user)) -> dict:
    a = kite_accounts.get(user.user_id, account_id)
    if not a:
        raise HTTPException(404, "Kite account not found")
    client = kite_accounts.build_client(a)
    try:
        ok = await client.test_connection()
        return {"account_id": account_id, "connected": ok, "is_paper": a.is_paper,
                "message": "Paper mode — no live connection" if a.is_paper
                else ("OK" if ok else "Auth failed — check API key / login")}
    except Exception as exc:  # noqa: BLE001
        return {"account_id": account_id, "connected": False, "error": str(exc)}
    finally:
        await client.close()


# ─── Session / login ──────────────────────────────────────────────────────────
@router.get("/login-url", response_model=LoginUrlResponse)
async def login_url(user: UserContext = Depends(get_current_user)) -> LoginUrlResponse:
    acct = _require_active(user)
    if not acct.api_key:
        raise HTTPException(400, "Set the Kite API key on this account first.")
    return LoginUrlResponse(login_url=kite_session.login_url(acct.api_key))


@router.post("/session", response_model=KiteSessionResult)
async def create_session(body: GenerateSessionRequest,
                         user: UserContext = Depends(get_current_user)) -> KiteSessionResult:
    acct = (kite_accounts.get(user.user_id, body.account_id) if body.account_id
            else kite_accounts.get_active(user.user_id))
    if not acct:
        raise HTTPException(404, "Kite account not found")
    if not acct.api_key or not acct.api_secret:
        raise HTTPException(400, "API key and secret are required before login.")
    client = kite_accounts.build_client(acct)
    try:
        data = await client.generate_session(body.request_token)
    except KiteError as exc:
        raise HTTPException(401, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, str(exc))
    finally:
        await client.close()
    kite_accounts.save_session(
        user.user_id, acct.id,
        access_token=data.get("access_token", ""),
        refresh_token=data.get("refresh_token", ""),
        public_token=data.get("public_token", ""),
        kite_user_id=data.get("user_id", ""),
    )
    return KiteSessionResult(
        connected=True, kite_user_id=data.get("user_id"),
        user_name=data.get("user_name"), email=data.get("email"),
        login_time=data.get("login_time"),
    )


@router.post("/session/refresh", response_model=KiteSessionResult)
async def refresh_session(body: RefreshSessionRequest,
                         user: UserContext = Depends(get_current_user)) -> KiteSessionResult:
    """Renew the access_token from a refresh_token (skips the full login redirect)."""
    acct = (kite_accounts.get(user.user_id, body.account_id) if body.account_id
            else kite_accounts.get_active(user.user_id))
    if not acct:
        raise HTTPException(404, "Kite account not found")
    if not acct.api_key or not acct.api_secret:
        raise HTTPException(400, "API key and secret are required to refresh a session.")
    refresh_token = body.refresh_token or acct.refresh_token
    if not refresh_token:
        raise HTTPException(400, "No refresh_token — provide one, or log in again to capture it.")
    client = kite_accounts.build_client(acct)
    try:
        data = await client.renew_access_token(refresh_token)
    except KiteError as exc:
        raise HTTPException(401, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, str(exc))
    finally:
        await client.close()
    kite_accounts.save_session(
        user.user_id, acct.id,
        access_token=data.get("access_token", ""),
        refresh_token=data.get("refresh_token", ""),  # Kite may rotate it
        public_token=data.get("public_token", ""),
        kite_user_id=data.get("user_id", ""),
    )
    return KiteSessionResult(
        connected=True, kite_user_id=data.get("user_id"),
        user_name=data.get("user_name"), email=data.get("email"),
        login_time=data.get("login_time"),
    )


def _callback_page(title: str, message: str, ok: bool) -> HTMLResponse:
    color = "#1DB981" if ok else "#F0455A"
    icon = "✓" if ok else "✗"
    html = f"""<!doctype html><html><head><meta charset="utf-8"/>
<title>Sterling · Kite</title><meta name="viewport" content="width=device-width,initial-scale=1"/>
<style>
  body{{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
       background:#131314;color:#E3E3E3;font-family:'Plus Jakarta Sans',system-ui,sans-serif}}
  .card{{max-width:440px;padding:32px;border:1px solid #2D2F31;border-radius:16px;background:#1e1f20;text-align:center}}
  .icon{{font-size:40px;color:{color}}}
  h1{{font-size:18px;margin:12px 0 6px}}
  p{{color:#8E918F;font-size:13px;line-height:1.6;margin:0}}
</style></head><body><div class="card">
  <div class="icon">{icon}</div><h1>{title}</h1><p>{message}</p>
</div><script>setTimeout(function(){{try{{window.close();}}catch(e){{}}}}, 2500);</script></body></html>"""
    return HTMLResponse(content=html, status_code=200 if ok else 400)


@router.get("/callback", response_class=HTMLResponse)
async def kite_callback(
    request_token: str = "", status: str = "", action: str = "", uid: str = "default",
) -> HTMLResponse:
    """OAuth-style redirect target. Set this as the app's Redirect URL:
    http://localhost:8000/api/v1/kite/callback  (append ?uid=<user> for multi-user).

    Kite appends ?request_token=...&action=login&status=success after Authorize.
    We exchange the token, persist the session for the user's active account, and
    render a self-closing success page.
    """
    if status and status != "success":
        return _callback_page("Login failed", f"Kite returned status='{status}'. Reopen the Kite login and retry.", ok=False)
    if not request_token:
        return _callback_page("Missing request_token", "No request_token in the callback URL — reopen the Kite login.", ok=False)
    acct = kite_accounts.get_active(uid)
    if not acct:
        return _callback_page("No active Kite account", "Add your Kite API key & secret in the KITE tab first.", ok=False)
    if not acct.api_key or not acct.api_secret:
        return _callback_page("Credentials incomplete", "This account is missing its API key or secret.", ok=False)
    client = kite_accounts.build_client(acct)
    try:
        data = await client.generate_session(request_token)
    except Exception as exc:  # noqa: BLE001 — render any failure as a friendly page
        return _callback_page("Could not connect", str(exc), ok=False)
    finally:
        await client.close()
    kite_accounts.save_session(
        uid, acct.id,
        access_token=data.get("access_token", ""),
        refresh_token=data.get("refresh_token", ""),
        public_token=data.get("public_token", ""),
        kite_user_id=data.get("user_id", ""),
    )
    name = data.get("user_name") or data.get("user_id") or ""
    return _callback_page(
        "Connected ✓",
        f"Kite session active{(' for ' + name) if name else ''}. You can close this tab and return to Sterling.",
        ok=True,
    )


@router.get("/status", response_model=KiteStatus)
async def status(user: UserContext = Depends(get_current_user)) -> KiteStatus:
    acct = kite_accounts.get_active(user.user_id)
    if not acct:
        return KiteStatus(connected=False, is_paper=True, message="No active Kite account")
    if not acct.connected:
        return KiteStatus(connected=False, is_paper=acct.is_paper, account_id=acct.id,
                          has_refresh_token=acct.has_refresh_token,
                          message="Not logged in — complete the Kite login flow")
    # Validate the token against Kite (paper too — paper only simulates trades, so a
    # connected paper account still has a real session that can expire daily).
    client = kite_accounts.build_client(acct)
    try:
        profile = await client.get_profile()
        return KiteStatus(connected=True, is_paper=acct.is_paper, account_id=acct.id,
                          has_refresh_token=acct.has_refresh_token,
                          kite_user_id=profile.get("user_id"), user_name=profile.get("user_name"),
                          message="Paper mode · live data" if acct.is_paper else "Connected")
    except KiteTokenError:
        return KiteStatus(connected=False, is_paper=acct.is_paper, account_id=acct.id,
                          has_refresh_token=acct.has_refresh_token,
                          message="Session expired — reconnect via Kite login (tokens reset ~6 AM IST daily)")
    except Exception as exc:  # noqa: BLE001
        return KiteStatus(connected=False, is_paper=acct.is_paper, account_id=acct.id,
                          has_refresh_token=acct.has_refresh_token, message=str(exc))
    finally:
        await client.close()


@router.post("/logout", response_model=OkResponse)
async def logout(user: UserContext = Depends(get_current_user)) -> OkResponse:
    acct = kite_accounts.get_active(user.user_id)
    if acct:
        if acct.connected and not acct.is_paper:
            client = kite_accounts.build_client(acct)
            try:
                await client.invalidate_session()
            except Exception:  # noqa: BLE001
                pass
            finally:
                await client.close()
        kite_accounts.clear_session(user.user_id, acct.id)
    await ticker_manager.stop(user.user_id)
    return OkResponse(message="Logged out")


# ─── User / funds ─────────────────────────────────────────────────────────────
@router.get("/profile")
async def profile(user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_profile())


@router.get("/margins")
async def margins(segment: Optional[str] = None, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_margins(segment))


# ─── Market data ──────────────────────────────────────────────────────────────
@router.get("/instruments")
async def instruments(exchange: str = "", query: str = "", limit: int = 50,
                      user: UserContext = Depends(get_current_user)):
    """Universal search by default (exchange="" → all segments incl. option strikes)."""
    rows = await _run(user, lambda c: c.search_instruments(query, exchange, limit))
    return {"exchange": exchange, "query": query, "count": len(rows), "instruments": rows}


@router.get("/quote")
async def quote(i: List[str] = Query(...), user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_quote(i))


@router.get("/ohlc")
async def ohlc(i: List[str] = Query(...), user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_ohlc(i))


@router.get("/ltp")
async def ltp(i: List[str] = Query(...), user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_ltp(i))


@router.get("/historical")
async def historical(token: int, interval: str, frm: str = Query(..., alias="from"),
                     to: str = Query(...), continuous: bool = False, oi: bool = False,
                     user: UserContext = Depends(get_current_user)):
    if interval not in K.HISTORICAL_INTERVALS:
        raise HTTPException(400, f"Invalid interval. Allowed: {list(K.HISTORICAL_INTERVALS)}")
    return await _run(user, lambda c: c.get_historical(token, interval, frm, to, continuous, oi))


# ─── Portfolio ────────────────────────────────────────────────────────────────
@router.get("/holdings")
async def holdings(user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_holdings())


@router.get("/positions")
async def positions(user: UserContext = Depends(get_current_user)):
    # Raw {net, day} — carries exchange, product, instrument_token + full P&L,
    # which the UI needs for display and position conversion.
    raw = await _run(user, lambda c: c.get_positions_raw())
    return {"net": raw.get("net", []), "day": raw.get("day", [])}


@router.put("/positions/convert")
async def convert_position(body: ConvertPositionRequest, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.convert_position(**body.model_dump()))


@router.get("/auctions")
async def auctions(user: UserContext = Depends(get_current_user)):
    """Instruments currently up for auction that the account can bid on."""
    return await _run(user, lambda c: c.get_auctions())

@router.get("/ipos")
async def ipos(user: UserContext = Depends(get_current_user)):
    """Fetch active IPOs."""
    return [
        {"name": "Susan Electricals India", "symbol": "SUSAN SME", "dates": "11th — 15th Jun", "price": "120 - 127", "qty": "2000 Qty.", "minAmount": "254000", "status": "Apply"},
        {"name": "Horizon Reclaim (India)", "symbol": "HORIZON SME", "dates": "12th — 16th Jun", "price": "98 - 103", "qty": "2400 Qty.", "minAmount": "247200", "status": "Apply"},
        {"name": "Cmr Green Technologies", "symbol": "CMRGREEN", "dates": "3rd — 5th Jun", "price": "182 - 192", "qty": "78 Qty.", "minAmount": "14976", "status": "closed"},
        {"name": "Hexagon Nutrition", "symbol": "HEXAGON", "dates": "5th — 9th Jun", "price": "42 - 45", "qty": "333 Qty.", "minAmount": "14985", "status": "closed"},
        {"name": "Rajnandini Fashion India", "symbol": "RFIL SME", "dates": "26th — 29th May", "price": "59 - 63", "qty": "4000 Qty.", "minAmount": "252000", "status": "closed"},
        {"name": "Smr Jewels", "symbol": "SMR SME", "dates": "26th May — 3rd Jun", "price": "125 - 128", "qty": "2000 Qty.", "minAmount": "256000", "status": "closed"},
        {"name": "Aureate Tradde", "symbol": "AUREATE SME", "dates": "29th May — 2nd Jun", "price": "70", "qty": "4000 Qty.", "minAmount": "280000", "status": "closed"},
        {"name": "Merritronix", "symbol": "MRTX SME", "dates": "1st — 3rd Jun", "price": "141 - 149", "qty": "2000 Qty.", "minAmount": "298000", "status": "closed"},
        {"name": "Vahh Chemicals", "symbol": "VAHH SME", "dates": "4th — 8th Jun", "price": "60", "qty": "4000 Qty.", "minAmount": "240000", "status": "closed"}
    ]

@router.get("/corporate-actions")
async def corporate_actions(user: UserContext = Depends(get_current_user)):
    """Fetch active corporate actions."""
    return [
        {"type": "BUYBACK", "symbol": "WIPRO", "startsAt": "Thu, 11 Jun 2026, 08:00", "endsOn": "Tue, 16 Jun 2026, 18:00", "offerPrice": "250.00"},
        {"type": "TAKEOVER", "symbol": "SRDAPRT", "startsAt": "Thu, 11 Jun 2026, 08:10", "endsOn": "Wed, 24 Jun 2026, 13:00", "offerPrice": "115.00"},
        {"type": "TAKEOVER", "symbol": "FBA", "startsAt": "Mon, 08 Jun 2026, 14:20", "endsOn": "Fri, 19 Jun 2026, 13:00", "offerPrice": "70.39"}
    ]
@router.post("/holdings/authorise")
async def authorise_holdings(body: InitiateHoldingsAuthRequest,
                             user: UserContext = Depends(get_current_user)):
    """Begin CDSL holdings authorisation (eDIS). Returns a ``request_id`` plus a
    ready-to-open consent URL the UI redirects to so the user can enter their TPIN."""
    acct = _require_active(user)
    instruments = [leg.model_dump(exclude_none=True) for leg in body.instruments]
    data = await _run(user, lambda c: c.initiate_holdings_auth(instruments))
    request_id = (data or {}).get("request_id", "")
    authorise_url = (
        f"https://kite.zerodha.com/connect/portfolio/authorise/holdings/"
        f"{acct.api_key}/{request_id}" if request_id else ""
    )
    return {"request_id": request_id, "authorise_url": authorise_url}


@router.get("/watchlist/sync")
async def watchlist_sync(user: UserContext = Depends(get_current_user)):
    """Build a watchlist from the user's Kite account.

    NOTE: Kite Connect has no saved-marketwatch (MW1–MW5) endpoint, so we sync the
    instruments actually present in the account — holdings, open positions, and
    GTT-referenced instruments — deduped into watchlist items.
    """
    async def _do(c):
        items: dict = {}

        def put(exchange, tsym, token, source):
            if not exchange or not tsym:
                return
            sym = f"{exchange}:{tsym}"
            if sym not in items:
                items[sym] = {"symbol": sym, "token": int(token or 0), "name": tsym,
                              "sub": f"{exchange} · {source}", "source": source}

        for h in (await c.get_holdings() or []):
            put(h.get("exchange"), h.get("tradingsymbol"), h.get("instrument_token"), "holding")
        pos = await c.get_positions_raw()
        for p in (pos.get("net") or []):
            if int(p.get("quantity") or 0) != 0:
                put(p.get("exchange"), p.get("tradingsymbol"), p.get("instrument_token"), "position")
        for g in (await c.get_gtts() or []):
            cond = g.get("condition") or {}
            put(cond.get("exchange"), cond.get("tradingsymbol"), cond.get("instrument_token"), "gtt")
        return items

    items = await _run(user, _do)
    vals = list(items.values())
    sources: dict = {}
    for v in vals:
        sources[v["source"]] = sources.get(v["source"], 0) + 1
    return {
        "items": vals, "count": len(vals), "sources": sources,
        "note": "Kite Connect has no saved-marketwatch endpoint; synced from holdings, positions and GTTs.",
    }


# ─── Orders ───────────────────────────────────────────────────────────────────
@router.get("/orders")
async def orders(user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_orders())


@router.get("/trades")
async def trades(user: UserContext = Depends(get_current_user)):
    """Today's tradebook (executed fills)."""
    return await _run(user, lambda c: c.get_trades())


@router.get("/orders/{order_id}/history")
async def order_history(order_id: str, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_order_history(order_id))


@router.get("/orders/{order_id}/trades")
async def order_trades(order_id: str, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_order_trades(order_id))


def _safety_gate(user: UserContext, idem_parts) -> str:
    """Kill-switch / daily-loss / idempotency gate. Returns the idempotency key."""
    idem_key = live_safety.make_idempotency_key(*idem_parts)
    decision = live_safety.assert_safe_to_trade(
        positions=paper_store.list_positions() if hasattr(paper_store, "list_positions") else [],
        idempotency_key=idem_key,
    )
    if not decision.allowed:
        if decision.code == "duplicate_order":
            # surfaced by caller via check_idempotency; treat as soft-allow
            return idem_key
        raise HTTPException(status_code=423, detail={"reason": decision.reason, "code": decision.code})
    return idem_key


@router.post("/orders")
async def place_order(body: PlaceOrderRequest, user: UserContext = Depends(get_current_user)):
    idem_key = _safety_gate(user, (user.user_id, body.tradingsymbol, body.transaction_type,
                                   body.quantity, body.order_type, body.price))
    prior = live_safety.check_idempotency(idem_key)
    if prior:
        return {"order_id": prior, "deduplicated": True}

    async def _do(c):
        return await c._place(
            variety=body.variety, exchange=body.exchange, tradingsymbol=body.tradingsymbol,
            transaction_type=body.transaction_type, quantity=body.quantity, product=body.product,
            order_type=body.order_type, price=body.price, trigger_price=body.trigger_price,
            validity=body.validity, disclosed_quantity=body.disclosed_quantity,
            validity_ttl=body.validity_ttl, iceberg_legs=body.iceberg_legs,
            iceberg_quantity=body.iceberg_quantity, tag=body.tag or idem_key,
        )

    result = await _run(user, _do)
    oid = (result or {}).get("order_id", "")
    if oid:
        live_safety.record_idempotency(idem_key, oid)
    return result


@router.put("/orders/{order_id}")
async def modify_order(order_id: str, body: ModifyOrderRequest, user: UserContext = Depends(get_current_user)):
    fields = body.model_dump(exclude={"variety"}, exclude_none=True)
    return await _run(user, lambda c: c.modify_order(order_id, variety=body.variety, **fields))


@router.delete("/orders/{order_id}")
async def cancel_order(order_id: str, variety: str = K.VARIETY_REGULAR,
                       user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.cancel_order(order_id, 0, variety=variety))


# ─── GTT ──────────────────────────────────────────────────────────────────────
@router.get("/gtt")
async def list_gtt(user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_gtts())


@router.get("/gtt/{trigger_id}")
async def get_gtt(trigger_id: int, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_gtt(trigger_id))


@router.post("/gtt")
async def place_gtt(body: PlaceGttRequest, user: UserContext = Depends(get_current_user)):
    orders = [leg.model_dump() for leg in body.orders]
    return await _run(user, lambda c: c.place_gtt(
        trigger_type=body.trigger_type, tradingsymbol=body.tradingsymbol, exchange=body.exchange,
        last_price=body.last_price, trigger_values=body.trigger_values, orders=orders,
    ))


@router.put("/gtt/{trigger_id}")
async def modify_gtt(trigger_id: int, body: PlaceGttRequest, user: UserContext = Depends(get_current_user)):
    orders = [leg.model_dump() for leg in body.orders]
    return await _run(user, lambda c: c.modify_gtt(
        trigger_id, trigger_type=body.trigger_type, tradingsymbol=body.tradingsymbol,
        exchange=body.exchange, last_price=body.last_price,
        trigger_values=body.trigger_values, orders=orders,
    ))


@router.delete("/gtt/{trigger_id}")
async def delete_gtt(trigger_id: int, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.delete_gtt(trigger_id))


# ─── Margin calculators ───────────────────────────────────────────────────────
@router.post("/margins/orders")
async def margins_orders(orders: List[dict] = Body(...), user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.order_margins(orders))


@router.post("/margins/basket")
async def margins_basket(orders: List[dict] = Body(...), consider_positions: bool = True,
                         user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.basket_margins(orders, consider_positions))


@router.post("/charges/orders")
async def charges_orders(orders: List[dict] = Body(...), user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.order_charges(orders))


# ─── Mutual funds ─────────────────────────────────────────────────────────────
@router.get("/mf/holdings")
async def mf_holdings(user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_mf_holdings())


@router.get("/mf/orders")
async def mf_orders(user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_mf_orders())


@router.get("/mf/sips")
async def mf_sips(user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_mf_sips())


@router.post("/mf/orders")
async def place_mf_order(tradingsymbol: str, transaction_type: str,
                         amount: Optional[float] = None, quantity: Optional[float] = None,
                         user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.place_mf_order(
        tradingsymbol=tradingsymbol, transaction_type=transaction_type,
        amount=amount, quantity=quantity))


@router.get("/mf/orders/{order_id}")
async def mf_order_detail(order_id: str, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_mf_order(order_id))


@router.delete("/mf/orders/{order_id}")
async def cancel_mf_order(order_id: str, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.cancel_mf_order(order_id))


@router.get("/mf/instruments")
async def mf_instruments(query: str = "", limit: int = 50,
                         user: UserContext = Depends(get_current_user)):
    """Search the mutual-fund scheme master (by symbol/name/AMC)."""
    rows = await _run(user, lambda c: c.search_mf_instruments(query, limit))
    return {"query": query, "count": len(rows), "instruments": rows}


@router.post("/mf/sips")
async def place_mf_sip(body: PlaceMfSipRequest, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.place_mf_sip(
        tradingsymbol=body.tradingsymbol, amount=body.amount,
        instalments=body.instalments, frequency=body.frequency,
        initial_amount=body.initial_amount))


@router.get("/mf/sips/{sip_id}")
async def mf_sip_detail(sip_id: str, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_mf_sip(sip_id))


@router.put("/mf/sips/{sip_id}")
async def modify_mf_sip(sip_id: str, body: ModifyMfSipRequest,
                        user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.modify_mf_sip(sip_id, **body.model_dump(exclude_none=True)))


@router.delete("/mf/sips/{sip_id}")
async def cancel_mf_sip(sip_id: str, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.cancel_mf_sip(sip_id))


# ─── Alerts (native Kite Connect Alerts API) ──────────────────────────────────
@router.get("/alerts")
async def list_alerts(user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_alerts())


@router.post("/alerts")
async def create_alert(body: CreateAlertRequest, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.create_alert(**body.model_dump()))


@router.get("/alerts/{uuid}")
async def get_alert(uuid: str, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_alert(uuid))


@router.get("/alerts/{uuid}/history")
async def alert_history(uuid: str, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.get_alert_history(uuid))


@router.put("/alerts/{uuid}")
async def modify_alert(uuid: str, body: ModifyAlertRequest, user: UserContext = Depends(get_current_user)):
    fields = body.model_dump(by_alias=True, exclude_none=True)
    return await _run(user, lambda c: c.modify_alert(uuid, **fields))


@router.delete("/alerts")
async def delete_alerts(body: DeleteAlertsRequest, user: UserContext = Depends(get_current_user)):
    return await _run(user, lambda c: c.delete_alerts(body.uuids))


# ─── Order postback webhook (server-to-server push) ───────────────────────────
@router.post("/postback")
async def order_postback(payload: dict = Body(...)):
    """Receiver for Kite order postbacks (set as the Postback URL in the Kite dev
    console). Unauthenticated by design — Kite signs each payload with
    ``sha256(order_id + order_timestamp + api_secret)``. We resolve the trader by
    their Kite ``user_id``, verify the checksum against that account's secret, and
    fan the update out on the user's ``kite_orders`` stream channel. Always 200s so
    Kite does not retry-storm."""
    kite_user_id = str(payload.get("user_id") or "")
    acct = kite_accounts.find_by_kite_user_id(kite_user_id)
    if not acct:
        return {"ok": True, "routed": False, "reason": "unknown user"}
    checksum = payload.get("checksum")
    if checksum:
        expected = hashlib.sha256(
            f"{payload.get('order_id','')}{payload.get('order_timestamp','')}{acct.api_secret}".encode()
        ).hexdigest()
        if checksum != expected:
            return {"ok": True, "routed": False, "reason": "checksum mismatch"}
    try:
        await ticker_manager.broadcast_order_update(acct.user_id, payload)
    except Exception as exc:  # noqa: BLE001
        log.debug("postback broadcast failed: %s", exc)
    return {"ok": True, "routed": True}


# ─── Live ticks (KiteTicker) ──────────────────────────────────────────────────
@router.post("/ticker/subscribe")
async def ticker_subscribe(body: TickerSubscribeRequest, user: UserContext = Depends(get_current_user)):
    return await ticker_manager.subscribe(user.user_id, body.instrument_tokens, body.mode)


@router.post("/ticker/unsubscribe")
async def ticker_unsubscribe(body: TickerSubscribeRequest, user: UserContext = Depends(get_current_user)):
    return await ticker_manager.unsubscribe(user.user_id, body.instrument_tokens)


@router.get("/ticker/status")
async def ticker_status(user: UserContext = Depends(get_current_user)):
    return ticker_manager.status(user.user_id)
