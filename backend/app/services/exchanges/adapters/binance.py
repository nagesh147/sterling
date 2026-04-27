"""
Binance USDT-M Futures adapter (https://fapi.binance.com).
Public: candles, mark price, index price.
Private: account balance, positions, open orders, trades.

Auth: X-MBX-APIKEY header + HMAC-SHA256 timestamp signature.
Docs: https://binance-docs.github.io/apidocs/futures/en/
"""
import hashlib
import hmac
import time
from typing import List, Optional

import httpx

from app.services.exchanges.authenticated_base import AuthenticatedExchangeAdapter
from app.schemas.market import Candle, OptionSummary
from app.schemas.instruments import InstrumentMeta
from app.schemas.account import (
    AssetBalance, AccountPosition, AccountOrder, AccountFill, PortfolioSnapshot,
)
from app.core.logging import get_logger

log = get_logger(__name__)

_FAPI = "https://fapi.binance.com"  # USDT-M Futures
_SPOT  = "https://api.binance.com"

_INTERVAL_MAP = {"15m": "15m", "1H": "1h", "4H": "4h"}


def _ts_ms(ts) -> int:
    ts = int(ts)
    return ts * 1000 if ts < 1_000_000_000_000 else ts


def _sign(secret: str, query_string: str) -> str:
    return hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()


def _add_signature(params: dict, secret: str) -> dict:
    params["timestamp"] = int(time.time() * 1000)
    qs = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    params["signature"] = _sign(secret, qs)
    return params


class BinanceAdapter(AuthenticatedExchangeAdapter):
    """
    Binance USDT-M Futures adapter.
    api_key + api_secret for account endpoints.
    Candles/prices work without credentials.
    is_paper=True returns mock account data.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        is_paper: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._is_paper = is_paper
        self._timeout = timeout
        self._fapi_client: Optional[httpx.AsyncClient] = None
        self._spot_client: Optional[httpx.AsyncClient] = None

    async def _fapi(self) -> httpx.AsyncClient:
        if self._fapi_client is None or self._fapi_client.is_closed:
            self._fapi_client = httpx.AsyncClient(
                base_url=_FAPI, timeout=self._timeout,
                headers={"User-Agent": "Sterling/1.0", "X-MBX-APIKEY": self._api_key},
            )
        return self._fapi_client

    async def _spot(self) -> httpx.AsyncClient:
        if self._spot_client is None or self._spot_client.is_closed:
            self._spot_client = httpx.AsyncClient(
                base_url=_SPOT, timeout=self._timeout,
                headers={"User-Agent": "Sterling/1.0"},
            )
        return self._spot_client

    async def _public_get(self, base: str, path: str, params: dict = None) -> dict | list:
        client = await (self._fapi() if base == "fapi" else self._spot())
        resp = await client.get(path, params=params or {})
        resp.raise_for_status()
        return resp.json()

    async def _auth_get(self, path: str, params: dict = None) -> dict | list:
        if self._is_paper or not self._api_key or not self._api_secret:
            raise RuntimeError("Account access requires api_key + api_secret with is_paper=False")
        p = _add_signature(dict(params or {}), self._api_secret)
        client = await self._fapi()
        resp = await client.get(path, params=p)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            raise RuntimeError(f"Binance error {data['code']}: {data.get('msg')}")
        return data

    # ─── BaseExchangeAdapter ─────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            await self._public_get("fapi", "/fapi/v1/ping")
            return True
        except Exception:
            return False

    async def get_index_price(self, instrument: InstrumentMeta) -> float:
        sym = f"{instrument.underlying}USDT"
        data = await self._public_get("fapi", "/fapi/v1/premiumIndex", {"symbol": sym})
        return float(data.get("indexPrice") or data.get("markPrice") or 0.0)

    async def get_spot_price(self, instrument: InstrumentMeta) -> float:
        return await self.get_index_price(instrument)

    async def get_perp_price(self, instrument: InstrumentMeta) -> float:
        sym = f"{instrument.underlying}USDT"
        data = await self._public_get("fapi", "/fapi/v1/premiumIndex", {"symbol": sym})
        return float(data.get("markPrice") or 0.0)

    async def get_candles(
        self,
        instrument: InstrumentMeta,
        resolution: str,
        limit: int = 200,
    ) -> List[Candle]:
        interval = _INTERVAL_MAP.get(resolution)
        if not interval:
            raise ValueError(f"Unsupported resolution: {resolution}")
        sym = f"{instrument.underlying}USDT"
        per_page = 1500  # Binance hard limit per request
        all_rows: list = []
        end_time: Optional[int] = None  # None = current time

        while len(all_rows) < limit:
            params: dict = {
                "symbol": sym,
                "interval": interval,
                "limit": min(per_page, limit - len(all_rows)),
            }
            if end_time is not None:
                params["endTime"] = end_time

            rows = await self._public_get("fapi", "/fapi/v1/klines", params)
            if not rows:
                break
            all_rows = list(rows) + all_rows  # prepend (older first)
            if len(rows) < params["limit"]:
                break  # no more history
            # Next page: fetch bars older than the oldest we have
            end_time = int(rows[0][0]) - 1  # oldest open_time - 1ms

        candles = []
        for row in all_rows:
            try:
                candles.append(Candle(
                    timestamp_ms=_ts_ms(row[0]),
                    open=float(row[1]), high=float(row[2]),
                    low=float(row[3]), close=float(row[4]),
                    volume=float(row[5]),
                ))
            except (IndexError, ValueError, TypeError):
                continue
        # Deduplicate and sort ascending (Binance returns oldest first per page)
        seen: set = set()
        unique = []
        for c in candles:
            if c.timestamp_ms not in seen:
                seen.add(c.timestamp_ms)
                unique.append(c)
        return sorted(unique, key=lambda c: c.timestamp_ms)[-limit:]

    async def get_option_chain(self, instrument: InstrumentMeta) -> List[OptionSummary]:
        log.info("Binance COIN-M options not implemented — returning empty chain")
        return []

    async def get_dvol(self, instrument: InstrumentMeta) -> Optional[float]:
        return None

    async def get_dvol_history(self, instrument: InstrumentMeta, days: int = 30) -> List[float]:
        return []

    # ─── AuthenticatedExchangeAdapter ─────────────────────────────────────────

    async def test_connection(self) -> bool:
        if self._is_paper:
            return True
        try:
            await self._auth_get("/fapi/v1/account")
            return True
        except Exception:
            return False

    async def get_balances(self) -> List[AssetBalance]:
        if self._is_paper:
            return _paper_balances()
        data = await self._auth_get("/fapi/v2/account")
        balances = []
        for a in data.get("assets", []):
            total = float(a.get("walletBalance") or 0.0)
            if total == 0:
                continue
            balances.append(AssetBalance(
                asset=str(a.get("asset", "")),
                available=float(a.get("availableBalance") or 0.0),
                locked=float(a.get("initialMargin") or 0.0),
                total=total,
                usd_value=float(a.get("walletBalance") or 0.0),
            ))
        return balances

    async def get_positions(self) -> List[AccountPosition]:
        if self._is_paper:
            return []
        rows = await self._auth_get("/fapi/v2/positionRisk")
        positions = []
        for p in rows:
            amt = float(p.get("positionAmt") or 0.0)
            if amt == 0:
                continue
            positions.append(AccountPosition(
                symbol=str(p.get("symbol", "")),
                underlying=str(p.get("symbol", ""))[:3],
                size=abs(amt),
                side="long" if amt > 0 else "short",
                entry_price=float(p.get("entryPrice") or 0.0),
                mark_price=float(p.get("markPrice") or 0.0),
                unrealized_pnl=float(p.get("unRealizedProfit") or 0.0),
                realized_pnl=0.0,
                margin=float(p.get("initialMargin") or 0.0),
                leverage=float(p.get("leverage") or 0.0) or None,
                position_type="perpetual",
            ))
        return positions

    async def get_open_orders(self, underlying: Optional[str] = None) -> List[AccountOrder]:
        if self._is_paper:
            return []
        params = {}
        if underlying:
            params["symbol"] = f"{underlying.upper()}USDT"
        rows = await self._auth_get("/fapi/v1/openOrders", params)
        orders = []
        for o in (rows if isinstance(rows, list) else []):
            try:
                orders.append(AccountOrder(
                    order_id=str(o.get("orderId", "")),
                    symbol=str(o.get("symbol", "")),
                    side=str(o.get("side", "")).lower(),
                    size=float(o.get("origQty") or 0.0),
                    price=float(o.get("price") or 0.0),
                    filled_size=float(o.get("executedQty") or 0.0),
                    status=str(o.get("status", "")).lower(),
                    order_type=str(o.get("type", "")).lower(),
                    created_at_ms=_ts_ms(o.get("time") or int(time.time() * 1000)),
                ))
            except (ValueError, TypeError):
                continue
        return orders

    async def get_fills(self, limit: int = 50) -> List[AccountFill]:
        if self._is_paper:
            return []
        rows = await self._auth_get("/fapi/v1/userTrades", {"limit": min(limit, 1000)})
        fills = []
        for f in (rows if isinstance(rows, list) else []):
            try:
                fills.append(AccountFill(
                    fill_id=str(f.get("id", "")),
                    order_id=str(f.get("orderId", "")),
                    symbol=str(f.get("symbol", "")),
                    side="buy" if f.get("buyer") else "sell",
                    size=float(f.get("qty") or 0.0),
                    price=float(f.get("price") or 0.0),
                    fee=float(f.get("commission") or 0.0),
                    fee_asset=str(f.get("commissionAsset") or "USDT"),
                    pnl=float(f.get("realizedPnl") or 0.0),
                    created_at_ms=_ts_ms(f.get("time") or int(time.time() * 1000)),
                ))
            except (ValueError, TypeError):
                continue
        return fills[:limit]

    async def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        balances = await self.get_balances()
        positions = await self.get_positions()
        orders = await self.get_open_orders()
        usdt = next((b for b in balances if b.asset == "USDT"), None)
        total_bal = usdt.total if usdt else sum(b.total for b in balances)
        unreal = sum(p.unrealized_pnl for p in positions)
        margin_used = sum(p.margin for p in positions)
        return PortfolioSnapshot(
            exchange="binance",
            display_name="Binance USDT-M Futures",
            total_balance_usd=round(total_bal, 2),
            unrealized_pnl_usd=round(unreal, 2),
            realized_pnl_usd=0.0,
            margin_used=round(margin_used, 2),
            margin_available=round(max(0.0, total_bal - margin_used), 2),
            positions_count=len(positions),
            open_orders_count=len(orders),
            balances=balances,
            timestamp_ms=int(time.time() * 1000),
        )

    async def close(self) -> None:
        for client in [self._fapi_client, self._spot_client]:
            if client and not client.is_closed:
                await client.aclose()


def _paper_balances() -> List[AssetBalance]:
    return [
        AssetBalance(asset="USDT", available=10000.0, locked=500.0, total=10500.0, usd_value=10500.0),
        AssetBalance(asset="BNB", available=2.5, locked=0.0, total=2.5, usd_value=None),
    ]
