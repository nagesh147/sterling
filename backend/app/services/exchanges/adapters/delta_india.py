"""
Delta Exchange India adapter — fixed all data issues.
Public: market data, tickers, option chain. Private: balances, positions, orders, fills.
API base: https://api.delta.exchange  Docs: https://docs.delta.exchange
"""
import hashlib
import hmac
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

_BASE = "https://api.delta.exchange"

_RESOLUTION_MAP = {
    "15m": "15m",
    "1H":  "1h",
    "4H":  "4h",
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
        self._product_id_cache: dict[str, int] = {}  # symbol → product_id, lives for process lifetime

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base, timeout=self._timeout,
                headers={"User-Agent": "Sterling/1.0", "Content-Type": "application/json"},
            )
        return self._client

    def _sign(self, method, path, query="", body=""):
        ts = int(time.time())
        # Delta Exchange signature: METHOD + timestamp + /path + ?query + body
        # Reference: github.com/delta-exchange/python-rest-client
        msg = method + str(ts) + path
        if query: msg += "?" + query
        if body:  msg += body
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

    def _raise_api_error(self, resp, path: str) -> None:
        """Raise a clear error with Delta's own error message when possible."""
        try:
            data = resp.json()
            if isinstance(data, dict):
                # Delta returns {"success":false,"error":{"code":"...","context":"..."}}
                err = data.get("error") or {}
                code = err.get("code") if isinstance(err, dict) else str(err)
                ctx  = err.get("context", "") if isinstance(err, dict) else ""
                if code:
                    raise RuntimeError(f"Delta API {resp.status_code} on {path}: {code}{' — ' + str(ctx) if ctx else ''}")
        except (ValueError, KeyError):
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

        # 1. Perpetuals only — small list, always includes BTCUSDT/ETHUSDT/etc.
        #    Note: Delta requires "contract_types" (plural) for this filter to work.
        data = await self._public_get("/v2/products", params={"contract_types": "perpetual_futures", "page_size": 100})
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

    async def place_order(
        self,
        symbol: str,
        side: str,           # "buy" or "sell"
        size: float,
        order_type: str = "market_order",  # "market_order" or "limit_order"
        limit_price: float | None = None,
        leverage: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        reduce_only: bool = False,
    ) -> dict:
        """
        Place an order on Delta Exchange India.
        Returns the order dict from the API.
        """
        product_id = await self.get_product_id(symbol)
        body: dict = {
            "product_id": product_id,
            "size": int(size),           # Delta uses integer contract size
            "side": side,                # "buy" / "sell"
            "order_type": order_type,
            "reduce_only": reduce_only,
        }
        if order_type == "limit_order" and limit_price is not None:
            body["limit_price"] = str(round(limit_price, 2))
        if leverage is not None:
            body["leverage"] = str(int(leverage))
        if stop_loss is not None:
            body["bracket_stop_loss_price"] = str(round(stop_loss, 2))
            body["bracket_stop_loss_limit_price"] = str(round(stop_loss * 0.999, 2))  # 0.1% slip
        if take_profit is not None:
            body["bracket_take_profit_price"] = str(round(take_profit, 2))
            body["bracket_take_profit_limit_price"] = str(round(take_profit * 0.999, 2))
        data = await self._auth_post("/v2/orders", body)
        return (data or {}).get("result") or {}

    async def cancel_order(self, order_id: str, product_id: int) -> dict:
        """Cancel an open order by ID."""
        data = await self._auth_delete(f"/v2/orders/{order_id}")
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

    async def get_index_price(self, instrument: InstrumentMeta) -> float:
        sym = instrument.delta_perp_symbol or f"{instrument.underlying}USD"
        data = await self._public_get(f"/v2/tickers/{sym}")
        t = (data or {}).get("result") or {}
        price = (
            t.get("spot_price") or
            t.get("index_price") or
            t.get("mark_price") or
            t.get("close") or
            t.get("last_price")
        )
        if not price:
            raise RuntimeError(f"No price field in Delta ticker response for {sym}: {list(t.keys())}")
        v = float(price)
        if v <= 0:
            raise RuntimeError(f"Delta ticker returned non-positive price {v} for {sym}")
        return v

    async def get_spot_price(self, instrument: InstrumentMeta) -> float:
        return await self.get_index_price(instrument)

    async def get_perp_price(self, instrument: InstrumentMeta) -> float:
        sym = instrument.delta_perp_symbol or f"{instrument.underlying}USD"
        data = await self._public_get(f"/v2/tickers/{sym}")
        t = (data or {}).get("result") or {}
        price = t.get("mark_price") or t.get("close") or t.get("last_price") or t.get("spot_price")
        if not price:
            raise RuntimeError(f"No price in Delta perp ticker for {sym}")
        return float(price)

    async def get_candles(self, instrument: InstrumentMeta,
                          resolution: str, limit: int = 200) -> List[Candle]:
        delta_res = _RESOLUTION_MAP.get(resolution)
        if not delta_res:
            raise ValueError(f"Unsupported resolution: {resolution}")
        try:
            sym = instrument.delta_perp_symbol or f"{instrument.underlying}USD"
            now = int(time.time())
            res_sec = {"15m": 900, "1h": 3600, "4h": 14400}[delta_res]
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
                oi = float(item.get("oi") or item.get("oi_contracts") or 0.0)
                vol = float(item.get("volume") or item.get("turnover") or 0.0)
                ts_raw = item.get("timestamp") or item.get("time") or now_ms
                options.append(OptionSummary(
                    instrument_name=symbol, underlying=instrument.underlying,
                    strike=strike, expiry_date=expiry_str, dte=dte,
                    option_type=opt_type, bid=bid, ask=ask,
                    mark_price=mark, mid_price=mid, mark_iv=iv, delta=delta_val,
                    open_interest=oi, volume_24h=vol, last_updated_ms=_ts_ms(ts_raw),
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

    async def get_fills(self, limit: int = 50) -> List[AccountFill]:
        if self._is_paper:
            return []
        data = await self._auth_get("/v2/fills", params={"page_size": min(limit, 100)})
        fills = []
        for f in ((data or {}).get("result") or []):
            try:
                fills.append(AccountFill(
                    fill_id=str(f.get("id") or ""), order_id=str(f.get("order_id") or ""),
                    symbol=str(f.get("product_symbol") or ""), side=str(f.get("side") or ""),
                    size=float(f.get("size") or 0.0), price=float(f.get("price") or 0.0),
                    fee=float(f.get("commission") or 0.0),
                    fee_asset=str((f.get("fee_asset") or {}).get("symbol") or "USD"),
                    pnl=float(f.get("pnl") or 0.0),
                    created_at_ms=_ts_ms(f.get("created_at") or int(time.time())),
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
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _paper_balances() -> List[AssetBalance]:
    return [
        AssetBalance(asset="BTC",  available=0.5,     locked=0.05, total=0.55,    usd_value=None),
        AssetBalance(asset="ETH",  available=5.0,     locked=0.5,  total=5.5,     usd_value=None),
        AssetBalance(asset="USDT", available=10000.0, locked=500.0, total=10500.0, usd_value=10500.0),
    ]
