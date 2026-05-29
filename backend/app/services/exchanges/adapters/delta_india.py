"""
Delta Exchange India adapter.
Public: market data, tickers, option chain. Private: balances, positions, orders, fills.
API base:  https://api.india.delta.exchange   Docs: https://docs.india.delta.exchange
WebSocket: wss://socket.india.delta.exchange  (public channels: v2/ticker, all_trades)

Public WS channels (no auth):
  v2/ticker   — 24h rolling OHLCV + mark/spot price, emitted every 5s
  all_trades  — real-time trade fills (last traded price on every fill)

Heartbeat: send {"type":"enable_heartbeat"} after subscribe;
           server sends {"type":"heartbeat"} every ~10s;
           reconnect if no message received within 35s.
"""
import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import List, Optional, Union

import httpx

from app.services.exchanges.authenticated_base import AuthenticatedExchangeAdapter
from app.schemas.market import Candle, OptionSummary
from app.schemas.instruments import InstrumentMeta
from app.schemas.account import (
    AssetBalance, AccountPosition, AccountOrder, AccountFill, PortfolioSnapshot
)
from app.core.logging import get_logger

log = get_logger(__name__)

_BASE   = "https://api.india.delta.exchange"
_WS_URL = "wss://socket.india.delta.exchange"

_RESOLUTION_MAP = {
    "1m":  "1m",
    "5m":  "5m",
    "15m": "15m",
    "1H":  "1h",
    "4H":  "4h",
    "D":   "1d",
    "1D":  "1d",
}


def _ts_ms(ts) -> int:
    """Normalize Delta timestamp (ISO string / epoch-s / epoch-ms) to milliseconds."""
    if isinstance(ts, str):
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except ValueError:
            pass
        try:
            return int(ts) * 1000
        except ValueError:
            return int(time.time() * 1000)
    ts_int = int(ts)
    return ts_int * 1000 if ts_int < 1_000_000_000_000 else ts_int


def _delta_dte(expiry_str: str) -> int:
    """
    Parse Delta option expiry → DTE.
    Handles: DDMMMYY (27DEC24), DDMMYY numeric (271224), ISO (2024-12-27).
    """
    if not expiry_str:
        return -1
    try:
        s = expiry_str.strip()
        if len(s) >= 10 and s[4:5] == "-":
            dt = datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        elif s.isdigit() and len(s) == 6:
            dt = datetime.strptime(s, "%d%m%y").replace(tzinfo=timezone.utc)
        else:
            dt = datetime.strptime(s.upper(), "%d%b%y").replace(tzinfo=timezone.utc)
        return max(0, (dt - datetime.now(timezone.utc)).days)
    except Exception:
        return -1


class DeltaIndiaAdapter(AuthenticatedExchangeAdapter):
    def __init__(self, api_key="", api_secret="", is_paper=True,
                 base_url=_BASE, timeout=10.0):
        self._api_key = api_key
        self._api_secret = api_secret
        self._is_paper = is_paper
        self._base = base_url
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._product_id_cache: dict[str, int] = {}

        # WebSocket live price cache — populated by _ws_loop, read by get_index_price
        self._ws_prices: dict[str, float] = {}
        self._ws_active  = False
        self._ws_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    # ─── WebSocket live price feed ────────────────────────────────────────────

    async def start_ws(self, symbols: list[str]) -> None:
        """Start (or restart) background WebSocket feed for live prices.
        Eliminates REST ticker calls while connected (~100× fewer API calls).
        Safe to call multiple times — stops old task first if still running."""
        if self._ws_task and not self._ws_task.done():
            # Already running — no-op (symbols are baked into the task)
            return
        self._ws_active = True
        self._ws_prices.clear()
        self._ws_task = asyncio.create_task(self._ws_loop(list(symbols)))
        ws_url = (
            "wss://socket.india.delta.exchange"
            if "india" in self._base
            else "wss://socket.delta.exchange"
        )
        log.info("Delta WS: starting feed → %s | symbols: %s", ws_url, symbols)

    async def stop_ws(self) -> None:
        """Gracefully stop the WebSocket feed."""
        self._ws_active = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except (asyncio.CancelledError, Exception):
                pass
            self._ws_task = None
        self._ws_prices.clear()

    async def _ws_loop(self, symbols: list[str]) -> None:
        """Persistent WebSocket loop with correct public channels and heartbeat."""
        import websockets  # local import — only needed when WS is active
        delay = 3.0

        # Derive WS URL from the REST base that was auto-detected during credential test.
        # India platform → wss://socket.india.delta.exchange
        # Global platform → wss://socket.delta.exchange
        ws_url = (
            "wss://socket.india.delta.exchange"
            if "india" in self._base
            else "wss://socket.delta.exchange"
        )

        # Delta WS heartbeat: reconnect if no message received within 35s.
        HEARTBEAT_TIMEOUT = 35.0

        while self._ws_active:
            try:
                async with websockets.connect(
                    ws_url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                    open_timeout=10,
                ) as ws:
                    # Subscribe to public market data channels (no auth required):
                    #   v2/ticker   — 24h OHLCV + mark/spot price, every 5s
                    #   all_trades  — real-time last-traded price on every fill
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "payload": {"channels": [
                            {"name": "v2/ticker",  "symbols": symbols},
                            {"name": "all_trades", "symbols": symbols},
                        ]},
                    }))
                    # Enable server-side heartbeat (server sends every ~10s)
                    await ws.send(json.dumps({"type": "enable_heartbeat"}))

                    delay = 3.0  # reset backoff on successful connect
                    log.info(
                        "Delta WS connected: %s | %d symbols | channels: v2/ticker, all_trades",
                        ws_url, len(symbols),
                    )

                    while self._ws_active:
                        try:
                            # Wait up to 35s for any message (heartbeat keeps this alive)
                            raw = await asyncio.wait_for(ws.recv(), timeout=HEARTBEAT_TIMEOUT)
                        except asyncio.TimeoutError:
                            log.warning(
                                "Delta WS: no message in %.0fs (heartbeat timeout) — reconnecting",
                                HEARTBEAT_TIMEOUT,
                            )
                            break  # reconnect

                        try:
                            msg   = json.loads(raw)
                            mtype = msg.get("type", "")

                            if mtype == "heartbeat":
                                continue  # keep-alive, no price data

                            sym = msg.get("symbol") or msg.get("product_symbol")
                            if not sym:
                                continue

                            if mtype == "v2/ticker":
                                # 5s snapshot: mark_price is the primary; fall back to spot/close
                                raw_price = (
                                    msg.get("mark_price") or
                                    msg.get("spot_price") or
                                    msg.get("close")
                                )
                            elif mtype == "all_trades":
                                # Real-time fill: last traded price
                                raw_price = msg.get("price")
                            else:
                                continue  # ignore unknown channel types

                            if raw_price:
                                v = float(raw_price)
                                if v > 0:
                                    self._ws_prices[sym] = v

                        except Exception:
                            continue  # ignore individual parse errors

            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._ws_active:
                    break
                log.debug("Delta WS disconnected (%s). Reconnecting in %.0fs.", exc, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60.0)

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base, timeout=self._timeout,
                headers={"User-Agent": "Sterling/1.0", "Content-Type": "application/json"},
            )
        return self._client

    def _sign(self, method, path, query="", body=""):
        ts = int(time.time())
        # Delta Exchange India signature format (from official Python REST client):
        #   message = method + timestamp + requestPath + queryString + requestBody
        # queryString is the raw query string WITHOUT the leading '?'.
        # Reference: github.com/delta-exchange/python-rest-client
        msg = method + str(ts) + path + query + body
        sig = hmac.new(
            self._api_secret.encode(), msg.encode(), digestmod=hashlib.sha256
        ).hexdigest()
        return sig, ts

    def _validate_response(self, data, path: str) -> dict:
        """Raise a clear error for all bad response shapes: None, non-dict, success=false."""
        if data is None:
            raise RuntimeError(f"Delta API returned null response for {path}")
        if isinstance(data, list):
            # Some Delta endpoints return a bare list — wrap it so callers use .get()
            return {"result": data}
        if not isinstance(data, dict):
            raise RuntimeError(f"Delta API returned unexpected type {type(data).__name__} for {path}")
        if data.get("success") is False:
            raise RuntimeError(f"Delta API error for {path}: {data.get('error', data)}")
        return data

    async def _public_get(self, path: str, params: Union[dict, list, None] = None) -> dict:
        client = await self._get_client()
        resp = await client.get(path, params=params or {})
        resp.raise_for_status()
        data = resp.json()
        return self._validate_response(data, path)

    # Human-readable messages for known Delta API error codes
    _FRIENDLY: dict[str, str] = {
        "insufficient_margin":    "Insufficient margin",
        "invalid_api_key":        "Invalid API key — check your credentials",
        "order_size_too_small":   "Order size too small for this contract",
        "order_size_too_large":   "Order size exceeds the maximum allowed",
        "market_closed":          "Market is currently closed",
        "post_only_reject":       "Order rejected — market would take immediately (post-only mode)",
        "self_trade_prevention":  "Order cancelled — would match your own open order",
        "risk_limit_exceeded":    "Position exceeds account risk limit",
        "ip_not_whitelisted":     "IP not whitelisted for this API key",
        "IpNotWhitelisted":       "IP not whitelisted for this API key",
    }

    @staticmethod
    async def _get_public_ip() -> str:
        """Fetch the server's outbound IP so users know what to whitelist."""
        import httpx as _httpx
        for url in ("https://api.ipify.org", "https://checkip.amazonaws.com"):
            try:
                async with _httpx.AsyncClient(timeout=3.0) as c:
                    r = await c.get(url)
                    ip = r.text.strip()
                    if ip:
                        return ip
            except Exception:
                pass
        return "unknown (check ifconfig.me)"

    def _raise_api_error(self, resp, path: str) -> None:
        """Raise a RuntimeError with a human-readable message for known Delta error codes."""
        try:
            data = resp.json()
            if isinstance(data, dict):
                err  = data.get("error") or {}
                code = (err.get("code") if isinstance(err, dict) else str(err)) or ""
                ctx  = err.get("context") if isinstance(err, dict) else None

                if code == "insufficient_margin" and isinstance(ctx, dict):
                    avail = float(ctx.get("available_balance", 0))
                    need  = float(ctx.get("required_additional_balance", 0))
                    asset = ctx.get("asset_symbol", "USD")
                    raise RuntimeError(
                        f"Insufficient margin — you have ${avail:.2f} {asset} available "
                        f"but need ${need:.2f} more. Add funds to your Delta Exchange account."
                    )

                if code in ("ip_not_whitelisted", "IpNotWhitelisted") or "whitelist" in code.lower():
                    raise RuntimeError("ip_not_whitelisted")

                if code:
                    friendly = self._FRIENDLY.get(code, code.replace("_", " ").capitalize())
                    ctx_str  = f" — {ctx}" if ctx and not isinstance(ctx, dict) else ""
                    raise RuntimeError(f"{friendly}{ctx_str}")
        except RuntimeError:
            raise
        except (ValueError, KeyError, TypeError):
            pass
        resp.raise_for_status()

    async def _auth_get(self, path, params=None):
        if self._is_paper or not self._api_key or not self._api_secret:
            raise RuntimeError("Account access requires valid credentials (is_paper=False)")
        query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        sig, ts = self._sign("GET", path, query)
        client = await self._get_client()
        resp = await client.get(path, params=params or {},
            headers={"api-key": self._api_key, "timestamp": str(ts), "signature": sig})
        if not resp.is_success:
            self._raise_api_error(resp, path)
        data = resp.json()
        return self._validate_response(data, path)

    async def _auth_post(self, path: str, body: dict) -> dict:
        if self._is_paper or not self._api_key or not self._api_secret:
            raise RuntimeError("Live trading requires valid Delta Exchange API credentials")
        import json as _json
        body_str = _json.dumps(body, separators=(',', ':'))
        sig, ts = self._sign("POST", path, body=body_str)
        client = await self._get_client()
        resp = await client.post(path, content=body_str,
            headers={
                "api-key": self._api_key, "timestamp": str(ts), "signature": sig,
                "Content-Type": "application/json",
            })
        if not resp.is_success:
            self._raise_api_error(resp, path)
        data = resp.json()
        return self._validate_response(data, path)

    async def _auth_delete(self, path: str) -> dict:
        if self._is_paper or not self._api_key or not self._api_secret:
            raise RuntimeError("Live trading requires valid Delta Exchange API credentials")
        sig, ts = self._sign("DELETE", path)
        client = await self._get_client()
        resp = await client.delete(path,
            headers={"api-key": self._api_key, "timestamp": str(ts), "signature": sig})
        resp.raise_for_status()
        data = resp.json()
        return self._validate_response(data, path)

    async def get_product_id(self, symbol: str) -> int:
        """Resolve a Delta product symbol to its integer product_id. Cached per-process."""
        if symbol in self._product_id_cache:
            return self._product_id_cache[symbol]

        def _scan(result):
            for p in (result or []):
                if str(p.get("symbol") or "") == symbol:
                    return int(p["id"])
            return None

        # 1. Perpetuals — Delta India has ~189 perpetuals (BTCUSD at position 189).
        #    Fetch with page_size=500 to get all in one call.
        data = await self._public_get("/v2/products", params={"contract_types": "perpetual_futures", "page_size": 500})
        pid = _scan((data or {}).get("result"))
        if pid is not None:
            self._product_id_cache[symbol] = pid
            return pid

        # 2. Options — fetch all expiry pages in parallel then scan
        import asyncio as _asyncio
        pages = await _asyncio.gather(*[
            self._public_get("/v2/products", params={"page_size": 200, "after": offset})
            for offset in (0, 200, 400, 600)
        ])
        for page in pages:
            pid = _scan((page or {}).get("result"))
            if pid is not None:
                self._product_id_cache[symbol] = pid
                return pid

        raise RuntimeError(f"Delta product not found for symbol: {symbol}")

    async def set_leverage(self, product_id: int, leverage: float) -> dict:
        """
        Set leverage for a product BEFORE placing orders.
        Must be called separately — Delta does not accept leverage inline in order body.
        POST /v2/products/{product_id}/orders/leverage
        """
        data = await self._auth_post(f"/v2/products/{product_id}/orders/leverage",
                                     {"leverage": str(int(leverage))})
        return (data or {}).get("result") or {}

    async def get_leverage(self, product_id: int) -> dict:
        """GET /v2/products/{product_id}/orders/leverage"""
        data = await self._auth_get(f"/v2/products/{product_id}/orders/leverage")
        return (data or {}).get("result") or {}

    async def set_margin_mode(self, product_id: int, mode: str = "isolated") -> dict:
        """Set the margin mode for a product BEFORE placing orders.

        `mode` is "isolated" (each position has its own margin pool — a bad
        trade can't cascade-liquidate the rest of the book) or "cross"
        (positions share margin — more efficient but contagious on a single
        blow-up). The derivatives selector enforces isolated-per-position
        as the default in OrderRouter._submit_live so a single mispriced
        contract can't take out the whole account.

        POST /v2/products/{product_id}/orders/margin_mode
        """
        if mode not in ("isolated", "cross"):
            raise ValueError(f"margin mode must be 'isolated' or 'cross', got {mode!r}")
        data = await self._auth_post(
            f"/v2/products/{product_id}/orders/margin_mode",
            {"margin_mode": mode},
        )
        return (data or {}).get("result") or {}

    async def cancel_all_orders(self, product_id: int) -> dict:
        """Cancel all open orders for a product. DELETE /v2/orders/all"""
        data = await self._auth_delete_with_body("/v2/orders/all", {"product_id": product_id})
        return (data or {})

    # ── Phase 3 derivatives build: live funding + L2 book ──────────────

    _FUNDING_CACHE_TTL_MS = 60_000

    @property
    def _funding_cache(self) -> dict[int, tuple[float, int]]:
        """Per-instance funding-rate cache. Lazily attached so existing
        constructors (paper/live + tests) don't need to touch __init__."""
        if not hasattr(self, "_funding_cache_dict"):
            self._funding_cache_dict = {}
        return self._funding_cache_dict

    async def get_funding_rate(self, product_id: int) -> dict:
        """Live funding rate for a perpetual product. Per-minute cached so
        the DerivativesSelector funding_cost_gate can run on every signal
        without flooding the REST endpoint.

        Returns a dict with at least:
          {"funding_rate_8h_pct": float (decimal), "fetched_ts_ms": int,
           "next_funding_ts_ms": int | None}

        Falls back to the funding.py static defaults when the live read
        fails (transient API hiccup); the gate still runs with stable
        inputs in that case.
        """
        import time as _t
        now_ms = int(_t.time() * 1000)
        cached = self._funding_cache.get(product_id)
        if cached is not None and (now_ms - cached[1]) < self._FUNDING_CACHE_TTL_MS:
            return {"funding_rate_8h_pct": cached[0],
                    "fetched_ts_ms": cached[1], "next_funding_ts_ms": None,
                    "source": "cache"}
        try:
            data = await self._public_get(
                f"/v2/products/{product_id}/funding_rate", params={}
            )
            result = (data or {}).get("result") or {}
            # DEI ships funding as an 8h rate (decimal). Sometimes as 'rate',
            # sometimes 'funding_rate', sometimes nested under 'current'.
            rate = float(
                result.get("rate") or
                result.get("funding_rate") or
                (result.get("current") or {}).get("rate") or
                0.0001
            )
            self._funding_cache[product_id] = (rate, now_ms)
            return {"funding_rate_8h_pct": rate,
                    "fetched_ts_ms": now_ms,
                    "next_funding_ts_ms": result.get("next_funding_ts_ms"),
                    "source": "live"}
        except Exception as exc:
            log.debug("get_funding_rate fallback for product %s: %s", product_id, exc)
            return {"funding_rate_8h_pct": 0.0001,
                    "fetched_ts_ms": now_ms,
                    "next_funding_ts_ms": None,
                    "source": "fallback", "error": str(exc)}

    async def get_l2_book(self, product_id: int, depth: int = 10) -> dict:
        """L2 order book for a product. Used by the selector's slippage
        estimator on options (book walks for multi-contract orders) and
        by the FE microstructure preview.

        Returns:
          {"bids": [[price, size], ...],
           "asks": [[price, size], ...],
           "ts_ms": int}
        """
        try:
            # DEI symbol-based L2 endpoint. We resolve product_id → symbol via
            # the product cache (populated on first get_product_id call).
            symbol = None
            for sym, pid in self._product_id_cache.items():
                if pid == product_id:
                    symbol = sym
                    break
            if symbol is None:
                # Brute-force lookup — costly but rare path
                data = await self._public_get(
                    "/v2/products", params={"page_size": 500}
                )
                for row in (data or {}).get("result") or []:
                    if int(row.get("id") or 0) == product_id:
                        symbol = row.get("symbol")
                        self._product_id_cache[symbol] = product_id
                        break
            if symbol is None:
                return {"bids": [], "asks": [], "ts_ms": 0,
                        "error": f"product_id {product_id} not found"}
            data = await self._public_get(
                f"/v2/l2orderbook/{symbol}", params={"depth": depth}
            )
            result = (data or {}).get("result") or {}
            return {
                "bids": [[float(b.get("price") or 0), float(b.get("size") or 0)]
                         for b in (result.get("buy") or [])[:depth]],
                "asks": [[float(a.get("price") or 0), float(a.get("size") or 0)]
                         for a in (result.get("sell") or [])[:depth]],
                "ts_ms": int(_ts_ms(result.get("timestamp") or 0)),
            }
        except Exception as exc:
            log.warning("get_l2_book failed for product %s: %s", product_id, exc)
            return {"bids": [], "asks": [], "ts_ms": 0, "error": str(exc)}

    async def _auth_delete_with_body(self, path: str, body: dict) -> dict:
        """DELETE with body — needed for /v2/orders/all."""
        if self._is_paper or not self._api_key or not self._api_secret:
            raise RuntimeError("Live trading requires valid Delta Exchange API credentials")
        import json as _json
        body_str = _json.dumps(body, separators=(',', ':'))
        sig, ts = self._sign("DELETE", path, body=body_str)
        client = await self._get_client()
        resp = await client.request("DELETE", path, content=body_str,
            headers={"api-key": self._api_key, "timestamp": str(ts), "signature": sig,
                     "Content-Type": "application/json"})
        if not resp.is_success:
            self._raise_api_error(resp, path)
        data = resp.json()
        return self._validate_response(data, path)

    async def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        order_type: str = "market_order",
        limit_price: float | None = None,
        leverage: float | None = None,
        time_in_force: str = "gtc",        # "gtc" or "ioc"
        post_only: bool = False,            # maker-only — strings "true"/"false" per API
        reduce_only: bool = False,          # strings "true"/"false" per API
        stop_loss: float | None = None,
        stop_loss_order_type: str = "market_order",
        stop_loss_limit_price: float | None = None,
        trail_amount: float | None = None,
        take_profit: float | None = None,
        take_profit_order_type: str = "market_order",
        take_profit_limit_price: float | None = None,
        bracket_trigger_method: str = "mark_price",
    ) -> dict:
        """
        Place an order on Delta Exchange India.
        Leverage is set via set_leverage() BEFORE this call (see flow in trading.py).
        """
        product_id = await self.get_product_id(symbol)
        body: dict = {
            "product_id": product_id,
            "size": int(size),
            "side": side,
            "order_type": order_type,
            # API requires string "true"/"false" for boolean flags
            "reduce_only": "true" if reduce_only else "false",
        }
        if order_type == "limit_order":
            if limit_price is not None:
                body["limit_price"] = str(round(limit_price, 2))
            body["time_in_force"] = time_in_force
            if post_only:
                body["post_only"] = "true"
        # Leverage no longer set here — must be set via set_leverage() first

        # Bracket trigger method
        has_bracket = take_profit is not None or stop_loss is not None or trail_amount is not None
        if has_bracket:
            body["bracket_stop_trigger_method"] = bracket_trigger_method

        # Take Profit
        if take_profit is not None:
            body["bracket_take_profit_price"] = str(round(take_profit, 2))
            if take_profit_order_type == "limit_order":
                lp = take_profit_limit_price if take_profit_limit_price else take_profit
                body["bracket_take_profit_limit_price"] = str(round(lp, 2))

        # Stop Loss (trail takes precedence over fixed price)
        if trail_amount is not None and trail_amount > 0:
            body["bracket_trail_amount"] = str(round(trail_amount, 2))
        elif stop_loss is not None:
            body["bracket_stop_loss_price"] = str(round(stop_loss, 2))
            if stop_loss_order_type == "limit_order":
                lp = stop_loss_limit_price if stop_loss_limit_price else stop_loss
                body["bracket_stop_loss_limit_price"] = str(round(lp, 2))

        data = await self._auth_post("/v2/orders", body)
        return (data or {}).get("result") or {}

    async def cancel_order(self, order_id: str, product_id: int) -> dict:
        """Cancel an open order. DELETE /v2/orders with body {id, product_id}."""
        data = await self._auth_delete_with_body("/v2/orders", {"id": int(order_id), "product_id": product_id})
        return (data or {}).get("result") or {}

    async def cancel_replace_stop(
        self,
        product_id: int,
        side: str,
        size: float,
        old_stop: float,
        new_stop: float,
        take_profit: float | None = None,
    ) -> dict:
        """
        Cancel existing bracket orders for this product and re-place a
        reduce-only limit order carrying the new bracket stop_loss.

        Delta India has no amend/order-edit endpoint, so the only
        idempotent approach is cancel-all-then-replace.  The carrier order
        is a deep reduce-only limit that, under normal conditions, will
        never fill — it exists only to carry the bracket stop to the OMS.
        """
        from datetime import datetime as _dt
        # 1. Cancel every open order for this product (bracket stops, TPs, etc.)
        try:
            await self.cancel_all_orders(product_id)
        except Exception:
            pass  # best-effort — existing stops will be overwritten by new bracket

        # 2. Place a reduce-only limit carrier ~10% away so it cannot fill
        #    under normal conditions.  The attached bracket_stop_loss becomes
        #    the active stop for the existing position.
        far_price = float(new_stop) * (1.10 if side == "sell" else 0.90)
        far_price = round(far_price, 2)

        bracket: dict = {
            "bracket_stop_loss_price": str(round(new_stop, 2)),
            "bracket_stop_trigger_method": "mark_price",
        }
        if take_profit is not None and take_profit > 0:
            bracket["bracket_take_profit_price"] = str(round(take_profit, 2))

        body = {
            "product_id": product_id,
            "size": int(size),
            "side": side,
            "order_type": "limit_order",
            "limit_price": str(far_price),
            "time_in_force": "gtc",
            "reduce_only": "true",
            **bracket,
        }
        data = await self._auth_post("/v2/orders", body)
        return (data or {}).get("result") or {}

    async def market_reduce_close(
        self,
        product_id: int,
        side: str,
        size: float,
    ) -> dict:
        """
        Place an immediate market order to reduce/close a portion of an
        existing position.  Side = "sell" to reduce a long, "buy" to cover
        a short.  `reduce_only` is forced to true so the OMS cannot
        accidentally flip the position direction.
        """
        body = {
            "product_id": product_id,
            "size": int(size),
            "side": side,
            "order_type": "market_order",
            "reduce_only": "true",
        }
        data = await self._auth_post("/v2/orders", body)
        return (data or {}).get("result") or {}

    async def place_order_option(
        self,
        option_symbol: str,  # e.g. "C-BTC-80000-050626"
        side: str,
        size: float,
        order_type: str = "market_order",
        limit_price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict:
        """Place an options order using the option contract symbol."""
        # Resolve product_id for this option
        data = await self._public_get("/v2/products", params={"contract_types": "call_options,put_options", "page_size": 500})
        product_id = None
        for p in ((data or {}).get("result") or []):
            if str(p.get("symbol") or "") == option_symbol:
                product_id = int(p["id"])
                break
        if product_id is None:
            raise RuntimeError(f"Option contract not found: {option_symbol}")
        body: dict = {
            "product_id": product_id,
            "size": int(size),
            "side": side,
            "order_type": order_type,
        }
        if order_type == "limit_order" and limit_price is not None:
            body["limit_price"] = str(round(limit_price, 6))
        if stop_loss is not None:
            body["bracket_stop_loss_price"] = str(round(stop_loss, 6))
        if take_profit is not None:
            body["bracket_take_profit_price"] = str(round(take_profit, 6))
        result = await self._auth_post("/v2/orders", body)
        return (result or {}).get("result") or {}

    # ─── BaseExchangeAdapter ──────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            await self._public_get("/v2/time")
            return True
        except Exception:
            try:
                await self._public_get("/v2/products", params={"page_size": 1})
                return True
            except Exception:
                return False

    @staticmethod
    def _pick_price(t: dict, *keys: str) -> float:
        """
        Extract the first positive price from a Delta ticker result dict.
        Handles strings ('103456.78'), ints, and floats. Skips None and zero.
        Raises RuntimeError if none of the keys yield a usable value.
        """
        for key in keys:
            raw = t.get(key)
            if raw is None:
                continue
            try:
                v = float(raw)
                if v > 0:
                    return v
            except (TypeError, ValueError):
                continue
        raise RuntimeError(
            f"No usable price in ticker result. "
            f"Tried keys {keys}. Available keys: {list(t.keys())}"
        )

    async def _fetch_ticker(self, sym: str) -> dict:
        """GET /v2/tickers/{sym} → result dict. Shared by price methods."""
        data = await self._public_get(f"/v2/tickers/{sym}")
        t = (data or {}).get("result")
        # result is a dict for single-symbol requests; defensive check
        if not isinstance(t, dict):
            raise RuntimeError(
                f"Delta ticker for {sym}: expected result dict, got {type(t).__name__}"
            )
        return t

    async def get_index_price(self, instrument: InstrumentMeta) -> float:
        sym = instrument.delta_perp_symbol or f"{instrument.underlying}USD"
        # Prefer live WS price (zero REST calls when connected)
        if sym in self._ws_prices:
            return self._ws_prices[sym]
        t = await self._fetch_ticker(sym)
        return self._pick_price(t, "spot_price", "mark_price", "close")

    async def get_spot_price(self, instrument: InstrumentMeta) -> float:
        return await self.get_index_price(instrument)

    async def get_perp_price(self, instrument: InstrumentMeta) -> float:
        sym = instrument.delta_perp_symbol or f"{instrument.underlying}USD"
        # Prefer live WS mark price
        if sym in self._ws_prices:
            return self._ws_prices[sym]
        t = await self._fetch_ticker(sym)
        return self._pick_price(t, "mark_price", "spot_price", "close")

    async def get_candles(self, instrument: InstrumentMeta,
                          resolution: str, limit: int = 200) -> List[Candle]:
        delta_res = _RESOLUTION_MAP.get(resolution)
        if not delta_res:
            raise ValueError(f"Unsupported resolution: {resolution}")
        # Seconds-per-bar lookup must match every key in _RESOLUTION_MAP. Adding
        # 1m / 5m / 1d here is the missing half of the Phase D extension — without
        # it Delta candle fetches raise KeyError('1m') (or '5m') on the first
        # request from scalping/intraday/positional modes.
        _RES_SECONDS = {
            "1m": 60, "5m": 300, "15m": 900,
            "1h": 3600, "4h": 14400,
            "1d": 86400,
        }
        try:
            sym = instrument.delta_perp_symbol or f"{instrument.underlying}USD"
            now = int(time.time())
            res_sec = _RES_SECONDS.get(delta_res)
            if res_sec is None:
                raise ValueError(f"Unsupported resolution mapping: {delta_res}")
            start = now - limit * res_sec
            data = await self._public_get(
                "/v2/history/candles",
                params={"symbol": sym, "resolution": delta_res, "start": start, "end": now},
            )
            candles = []
            for row in ((data or {}).get("result") or []):
                try:
                    if isinstance(row, (list, tuple)):
                        ts_ms = _ts_ms(row[0])
                        o, h, l, c = float(row[1]), float(row[2]), float(row[3]), float(row[4])
                        vol = float(row[5]) if len(row) > 5 else 0.0
                    else:
                        ts_ms = _ts_ms(row["time"])
                        o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
                        vol = float(row.get("volume", 0.0))
                    candles.append(Candle(timestamp_ms=ts_ms, open=o, high=h, low=l, close=c, volume=vol))
                except (KeyError, ValueError, TypeError, IndexError):
                    continue
            return sorted(candles, key=lambda c: c.timestamp_ms)
        except Exception as exc:
            log.error("Delta candles fetch failed for %s %s: %s", instrument.delta_perp_symbol, resolution, exc)
            raise

    async def get_option_chain(self, instrument: InstrumentMeta) -> List[OptionSummary]:
        if not instrument.has_options:
            return []
        ul = instrument.delta_option_underlying or instrument.underlying
        now_ms = int(time.time() * 1000)
        seen: set = set()
        items: List[dict] = []

        # Fetch call and put tickers using singular contract_type param (array form → 500)
        for ct in ("call_options", "put_options"):
            try:
                data = await self._public_get("/v2/tickers",
                                              params={"contract_type": ct, "page_size": 500})
                rows = (data or {}).get("result") or []
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    sym = str(row.get("symbol") or "")
                    if sym in seen:
                        continue
                    ua_sym = str(row.get("underlying_asset_symbol") or "")
                    # Filter to this underlying — Delta symbol format: C-BTC-79400-050526
                    if (ua_sym.upper() == ul.upper()
                            or sym.startswith(f"C-{ul.upper()}-")
                            or sym.startswith(f"P-{ul.upper()}-")):
                        seen.add(sym)
                        items.append(row)
            except Exception as exc:
                log.debug("Delta option tickers fetch (%s, %s): %s", ul, ct, exc)

        if not items:
            log.info("Delta option chain: no items for %s (options may not be live)", ul)
            return []

        options: List[OptionSummary] = []
        for item in items:
            try:
                symbol = item.get("symbol", "")
                # Delta symbol: C-BTC-79400-050526 or P-ETH-3200-280625
                parts = symbol.split("-")
                if len(parts) != 4 or parts[0] not in ("C", "P"):
                    continue
                opt_type = "call" if parts[0] == "C" else "put"
                strike = float(parts[2])
                expiry_str = parts[3]
                dte = _delta_dte(expiry_str)
                if dte < 0:
                    continue

                mark = float(item.get("mark_price") or item.get("close") or 0.0)
                # bid/ask live in nested quotes dict
                quotes = item.get("quotes") or {}
                bid = float(quotes.get("best_bid") or item.get("bid") or 0.0)
                ask = float(quotes.get("best_ask") or item.get("ask") or 0.0)
                mid = (bid + ask) / 2 if bid > 0 and ask > 0 else mark

                greeks = item.get("greeks") or {}
                iv = float(
                    item.get("mark_vol") or
                    item.get("mark_iv") or
                    greeks.get("iv") or
                    0.0
                )
                delta_val = float(greeks.get("delta") or item.get("delta") or 0.0)
                # Phase 1: pull gamma/vega/theta/rho out of DEI's greeks block
                # when present. Missing fields stay at 0; downstream
                # `enrich_with_greeks` BSM-fills them and stamps
                # greeks_enriched=True. Phase 0's OptionSummary defaults all
                # of these to 0 so an adapter response that ships only delta+iv
                # still validates the schema.
                gamma_val = float(greeks.get("gamma") or 0.0)
                vega_val  = float(greeks.get("vega")  or 0.0)
                theta_val = float(greeks.get("theta") or 0.0)
                rho_val   = float(greeks.get("rho")   or 0.0)
                oi = float(item.get("oi") or item.get("oi_contracts") or 0.0)
                vol = float(item.get("volume") or item.get("turnover") or 0.0)
                ts_raw = item.get("timestamp") or item.get("time") or now_ms
                # Spread% pre-computed once here so liquidity scoring and
                # microstructure veto don't re-derive bid/ask per call.
                spread_pct = ((ask - bid) / mid) if (bid > 0 and ask > 0 and mid > 0) else 0.0
                options.append(OptionSummary(
                    instrument_name=symbol, underlying=instrument.underlying,
                    strike=strike, expiry_date=expiry_str, dte=dte,
                    option_type=opt_type, bid=bid, ask=ask,
                    mark_price=mark, mid_price=mid, mark_iv=iv, delta=delta_val,
                    open_interest=oi, volume_24h=vol, last_updated_ms=_ts_ms(ts_raw),
                    gamma=gamma_val, vega=vega_val, theta=theta_val, rho=rho_val,
                    spread_pct=spread_pct,
                ))
            except (ValueError, TypeError, KeyError):
                continue
        return options

    async def get_dvol(self, instrument: InstrumentMeta) -> Optional[float]:
        return None  # No DVOL; HV-IVR fallback used instead

    async def get_dvol_history(self, instrument: InstrumentMeta, days: int = 30) -> List[float]:
        return []

    # ─── AuthenticatedExchangeAdapter ─────────────────────────────────────

    async def test_connection(self) -> bool:
        if self._is_paper:
            return True
        try:
            return bool((await self._auth_get("/v2/profile")).get("result"))
        except Exception:
            return False

    async def get_balances(self) -> List[AssetBalance]:
        if self._is_paper:
            return _paper_balances()
        data = await self._auth_get("/v2/wallet/balances")
        balances = []
        for w in ((data or {}).get("result") or []):
            try:
                balances.append(AssetBalance(
                    asset=str(w.get("asset_symbol") or (w.get("asset") or {}).get("symbol", "?")),
                    available=float(w.get("available_balance") or 0.0),
                    locked=float(w.get("order_margin") or 0.0),
                    total=float(w.get("balance") or 0.0), usd_value=None,
                ))
            except (ValueError, TypeError):
                continue
        return balances

    async def get_positions(self) -> List[AccountPosition]:
        if self._is_paper:
            return []
        data = await self._auth_get("/v2/positions/margined")
        positions = []
        for p in ((data or {}).get("result") or []):
            try:
                size = float(p.get("size") or 0.0)
                if size == 0:
                    continue
                positions.append(AccountPosition(
                    symbol=str(p.get("product_symbol") or ""),
                    underlying=str((p.get("underlying_asset") or {}).get("symbol") or ""),
                    size=abs(size), side="long" if size > 0 else "short",
                    entry_price=float(p.get("entry_price") or 0.0),
                    mark_price=float(p.get("mark_price") or 0.0),
                    unrealized_pnl=float(p.get("unrealized_pnl") or 0.0),
                    realized_pnl=float(p.get("realized_pnl") or 0.0),
                    margin=float(p.get("initial_margin") or 0.0),
                    leverage=float((p.get("leverage") or {}).get("value") or 0.0) or None,
                    position_type=str(p.get("product_type") or "unknown"),
                    created_at_ms=None,
                ))
            except (ValueError, TypeError):
                continue
        return positions

    async def get_open_orders(self, underlying: Optional[str] = None) -> List[AccountOrder]:
        if self._is_paper:
            return []
        params: dict = {"state": "open"}
        if underlying:
            params["underlying_asset_symbol"] = underlying
        data = await self._auth_get("/v2/orders", params=params)
        orders = []
        for o in ((data or {}).get("result") or []):
            try:
                orders.append(AccountOrder(
                    order_id=str(o.get("id") or ""), symbol=str(o.get("product_symbol") or ""),
                    side=str(o.get("side") or ""), size=float(o.get("size") or 0.0),
                    price=float(o.get("limit_price") or 0.0),
                    filled_size=float(o.get("size") or 0.0) - float(o.get("unfilled_size") or 0.0),
                    status=str(o.get("state") or "open"),
                    order_type=str(o.get("order_type") or "limit"),
                    created_at_ms=_ts_ms(o.get("created_at") or int(time.time())),
                ))
            except (ValueError, TypeError):
                continue
        return orders

    async def get_trading_preferences(self) -> dict:
        """
        GET /v2/users/trading_preferences
        Returns VIP level, discount factor, DETO setting, 30-day volume.
        """
        if self._is_paper or not self._api_key:
            return {}
        try:
            data = await self._auth_get("/v2/users/trading_preferences")
            return (data or {}).get("result") or {}
        except Exception:
            return {}

    async def _get_product_fee_info(self, symbol: str) -> dict:
        """
        Fetch taker/maker rates and contract_value for a product.
        Cached per symbol for the process lifetime.
        """
        cache_key = f"_fee_{symbol}"
        if hasattr(self, "_fee_cache") and cache_key in self._fee_cache:
            return self._fee_cache[cache_key]
        try:
            data = await self._public_get(f"/v2/products/{symbol}")
            r    = (data or {}).get("result") or {}
            info = {
                "contract_value":   float(r.get("contract_value") or 0.001),
                "notional_type":    str(r.get("notional_type") or "vanilla"),
                "taker_rate":       float(r.get("taker_commission_rate") or 0.0005),
                "maker_rate":       float(r.get("maker_commission_rate") or 0.0002),
                "settling_asset":   str((r.get("settling_asset") or {}).get("symbol") or "USD"),
            }
        except Exception:
            info = {
                "contract_value": 0.001, "notional_type": "vanilla",
                "taker_rate": 0.0005,    "maker_rate": 0.0002,
                "settling_asset": "USD",
            }
        if not hasattr(self, "_fee_cache"):
            self._fee_cache: dict = {}
        self._fee_cache[cache_key] = info
        return info

    async def get_fills(self, limit: int = 50) -> List[AccountFill]:
        if self._is_paper:
            return []
        from app.services.fees import decode_fill_fee
        data = await self._auth_get("/v2/fills", params={"page_size": min(limit, 100)})
        fills = []
        for f in ((data or {}).get("result") or []):
            try:
                symbol   = str(f.get("product_symbol") or "")
                fee_info = await self._get_product_fee_info(symbol)
                settling = str(f.get("settling_asset_symbol") or fee_info["settling_asset"])

                breakdown = decode_fill_fee(
                    f,
                    contract_value=fee_info["contract_value"],
                    notional_type=fee_info["notional_type"],
                )

                fills.append(AccountFill(
                    fill_id   = str(f.get("id") or ""),
                    order_id  = str(f.get("order_id") or ""),
                    symbol    = symbol,
                    side      = str(f.get("side") or ""),
                    size      = float(f.get("size") or 0.0),
                    price     = float(f.get("price") or 0.0),
                    fee       = breakdown.net_commission,
                    fee_asset = settling,
                    pnl       = float(f.get("pnl") or 0.0),
                    created_at_ms = _ts_ms(f.get("created_at") or int(time.time())),
                    # Detailed fee breakdown
                    fill_type        = breakdown.fill_type,
                    role             = breakdown.role,
                    notional_usd     = round(breakdown.notional_usd, 4),
                    gross_commission = round(breakdown.gross_commission, 6),
                    liquidation_fee  = round(breakdown.liquidation_fee, 6),
                    effective_rate   = round(breakdown.effective_rate, 8),
                    deto_discount    = round(breakdown.deto_discount, 6),
                    tfc_used         = round(breakdown.tfc_used, 6),
                    vip_discount     = round(breakdown.vip_discount, 6),
                    gst_amount       = round(breakdown.gst_amount, 6),
                    total_cost       = round(breakdown.total_cost, 6),
                    total_with_gst   = round(breakdown.total_with_gst, 6),
                    settling_asset   = breakdown.settling_asset,
                ))
            except (ValueError, TypeError):
                continue
        return fills

    async def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        balances = await self.get_balances()
        positions = await self.get_positions()
        orders = await self.get_open_orders()
        total_bal = sum(b.total for b in balances)
        unreal = sum(p.unrealized_pnl for p in positions)
        real = sum(p.realized_pnl for p in positions)
        margin_used = sum(p.margin for p in positions)
        usd = next((b for b in balances if b.asset in ("USDT", "USD", "INR")), None)
        margin_avail = usd.available if usd else max(0.0, total_bal - margin_used)
        return PortfolioSnapshot(
            exchange="delta_india", display_name="Delta Exchange India",
            total_balance_usd=round(total_bal, 2), unrealized_pnl_usd=round(unreal, 2),
            realized_pnl_usd=round(real, 2), margin_used=round(margin_used, 2),
            margin_available=round(margin_avail, 2), positions_count=len(positions),
            open_orders_count=len(orders), balances=balances,
            timestamp_ms=int(time.time() * 1000),
        )

    async def close(self) -> None:
        await self.stop_ws()
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _paper_balances() -> List[AssetBalance]:
    return [
        AssetBalance(asset="BTC",  available=0.5,     locked=0.05, total=0.55,    usd_value=None),
        AssetBalance(asset="ETH",  available=5.0,     locked=0.5,  total=5.5,     usd_value=None),
        AssetBalance(asset="USDT", available=10000.0, locked=500.0, total=10500.0, usd_value=10500.0),
    ]
