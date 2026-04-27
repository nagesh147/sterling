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

    async def _get_client(self):
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base, timeout=self._timeout,
                headers={"User-Agent": "Sterling/1.0", "Content-Type": "application/json"},
            )
        return self._client

    def _sign(self, method, path, query="", body=""):
        ts = int(time.time())
        msg = method + str(ts) + path
        if query: msg += "?" + query
        if body:  msg += body
        sig = hmac.new(
            self._api_secret.encode(), msg.encode(), digestmod=hashlib.sha256
        ).hexdigest()
        return sig, ts

    async def _public_get(self, path: str, params: Union[dict, list, None] = None) -> dict:
        client = await self._get_client()
        resp = await client.get(path, params=params or {})
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError(f"Delta API error: {data.get('error', data)}")
        return data

    async def _auth_get(self, path, params=None):
        if self._is_paper or not self._api_key or not self._api_secret:
            raise RuntimeError("Account access requires valid credentials (is_paper=False)")
        query = "&".join(f"{k}={v}" for k, v in (params or {}).items())
        sig, ts = self._sign("GET", path, query)
        client = await self._get_client()
        resp = await client.get(path, params=params or {},
            headers={"api-key": self._api_key, "timestamp": str(ts), "signature": sig})
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError(f"Delta auth error: {data.get('error', data)}")
        return data

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
        try:
            data = await self._public_get(f"/v2/tickers/{sym}")
            t = data.get("result", {})
            return float(t.get("spot_price") or t.get("index_price") or t.get("mark_price") or 0.0)
        except Exception:
            return 0.0

    async def get_spot_price(self, instrument: InstrumentMeta) -> float:
        return await self.get_index_price(instrument)

    async def get_perp_price(self, instrument: InstrumentMeta) -> float:
        sym = instrument.delta_perp_symbol or f"{instrument.underlying}USD"
        try:
            data = await self._public_get(f"/v2/tickers/{sym}")
            t = data.get("result", {})
            return float(t.get("mark_price") or t.get("close") or t.get("last_price") or 0.0)
        except Exception:
            return 0.0

    async def get_candles(self, instrument: InstrumentMeta,
                          resolution: str, limit: int = 200) -> List[Candle]:
        delta_res = _RESOLUTION_MAP.get(resolution)
        if not delta_res:
            raise ValueError(f"Unsupported resolution: {resolution}")
        sym = instrument.delta_perp_symbol or f"{instrument.underlying}USD"
        now = int(time.time())
        res_sec = {"15m": 900, "1h": 3600, "4h": 14400}[delta_res]
        start = now - limit * res_sec
        data = await self._public_get(
            "/v2/history/candles",
            params={"symbol": sym, "resolution": delta_res, "start": start, "end": now},
        )
        candles = []
        for row in data.get("result", []):
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

    async def get_option_chain(self, instrument: InstrumentMeta) -> List[OptionSummary]:
        if not instrument.has_options:
            return []
        ul = instrument.delta_option_underlying or instrument.underlying
        now_ms = int(time.time() * 1000)
        items: List[dict] = []

        # Strategy 1: dedicated endpoint
        try:
            data = await self._public_get("/v2/options/chain",
                                          params={"underlying_asset_symbol": ul})
            items = data.get("result", [])
        except Exception:
            pass

        # Strategy 2: filter tickers by contract type
        if not items:
            try:
                cd = await self._public_get("/v2/tickers",
                                            params=[("contract_types[]", "call_options")])
                pd = await self._public_get("/v2/tickers",
                                            params=[("contract_types[]", "put_options")])
                for t in cd.get("result", []) + pd.get("result", []):
                    asset = ((t.get("product") or {}).get("underlying_asset") or {})
                    if (asset.get("symbol", "").upper() == ul.upper()
                            or ul.upper() in t.get("symbol", "").upper()):
                        items.append(t)
            except Exception as exc:
                log.warning("Delta option chain failed for %s: %s", ul, exc)
                return []

        options: List[OptionSummary] = []
        for item in items:
            try:
                symbol = item.get("symbol", "")
                parts = symbol.split("-")
                if len(parts) != 4:
                    continue
                opt_type = "call" if parts[0] == "C" else "put"
                strike = float(parts[2])
                expiry_str = parts[3]
                dte = _delta_dte(expiry_str)
                if dte < 0:
                    continue
                bid = float(item.get("bid") or 0.0)
                ask = float(item.get("ask") or 0.0)
                mark = float(item.get("mark_price") or item.get("close") or 0.0)
                mid = (bid + ask) / 2 if bid > 0 and ask > 0 else mark
                greeks = item.get("greeks") or {}
                iv = float(item.get("mark_iv") or greeks.get("iv") or greeks.get("mark_iv")
                           or item.get("implied_volatility") or 0.0)
                delta_val = float(greeks.get("delta") or item.get("delta") or 0.0)
                oi = float(item.get("oi") or item.get("open_interest") or 0.0)
                vol = float(item.get("volume") or 0.0)
                ts_raw = item.get("created_at") or item.get("timestamp") or now_ms
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
        for w in data.get("result", []):
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
        for p in data.get("result", []):
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
        for o in data.get("result", []):
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
        for f in data.get("result", []):
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
