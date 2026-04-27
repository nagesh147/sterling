"""
Zerodha Kite adapter (India).
Auth: X-Kite-Version: 3 + Authorization: token {api_key}:{access_token}
access_token is obtained via Kite login flow (daily session).

Store in ExchangeConfig:
  api_key    = Kite API key (permanent)
  api_secret = Kite API secret (used to generate access_token checksum)
  extra      = {"access_token": "<session_token>"}

Docs: https://kite.trade/docs/connect/v3/
"""
import time
from datetime import datetime, timedelta, timezone
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

_BASE = "https://api.kite.trade"

# Zerodha interval names
_RESOLUTION_MAP = {
    "15m": "15minute",
    "1H":  "60minute",
    "4H":  "60minute",   # aggregate 4 × 60min bars → 4H on client side
    "1D":  "day",
}

# India VIX daily close (approx 30-day data)
_INDIA_VIX_TOKEN = 264969


def _ts_ms(ts) -> int:
    ts_int = int(ts)
    return ts_int * 1000 if ts_int < 1_000_000_000_000 else ts_int


def _parse_kite_ts(ts_str: str) -> int:
    """Parse Zerodha timestamp '2024-01-15 09:15:00+0530' → epoch ms."""
    try:
        # Kite returns '2024-01-15 09:15:00+0530'
        dt = datetime.fromisoformat(ts_str.replace("+0530", "+05:30"))
        return int(dt.timestamp() * 1000)
    except Exception:
        return int(time.time() * 1000)


def _aggregate_4h(candles_1h: List[Candle]) -> List[Candle]:
    """Group 1H candles into 4H buckets."""
    if not candles_1h:
        return []
    result: List[Candle] = []
    buf: List[Candle] = []
    for c in candles_1h:
        buf.append(c)
        if len(buf) == 4:
            result.append(Candle(
                timestamp_ms=buf[0].timestamp_ms,
                open=buf[0].open,
                high=max(x.high for x in buf),
                low=min(x.low for x in buf),
                close=buf[-1].close,
                volume=sum(x.volume for x in buf),
            ))
            buf = []
    return result


class ZerodhaAdapter(AuthenticatedExchangeAdapter):
    """
    Zerodha Kite Connect v3.
    api_key  — permanent Kite API key
    api_secret — API secret (needed to compute checksum at login)
    access_token — session token from extra dict (refreshed via Kite login)
    is_paper — True → mock responses
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        access_token: str = "",
        is_paper: bool = True,
        base_url: str = _BASE,
        timeout: float = 10.0,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._access_token = access_token
        self._is_paper = is_paper
        self._base = base_url
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                timeout=self._timeout,
                headers={
                    "X-Kite-Version": "3",
                    "User-Agent": "Sterling/1.0",
                },
            )
        return self._client

    def _auth_headers(self) -> dict:
        return {"Authorization": f"token {self._api_key}:{self._access_token}"}

    async def _auth_get(self, path: str, params: dict = None) -> dict:
        if self._is_paper or not self._api_key or not self._access_token:
            raise RuntimeError(
                "Account access requires valid api_key and access_token "
                "(set is_paper=False and provide access_token in extra config)"
            )
        client = await self._get_client()
        resp = await client.get(path, params=params or {}, headers=self._auth_headers())
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "error":
            raise RuntimeError(f"Kite error: {data.get('message', data)}")
        return data.get("data", data)

    # ─── BaseExchangeAdapter ────────────────────────────────────────────────

    async def ping(self) -> bool:
        if self._is_paper:
            return True
        try:
            client = await self._get_client()
            resp = await client.get("/")
            return resp.status_code < 500
        except Exception:
            return False

    async def get_index_price(self, instrument: InstrumentMeta) -> float:
        sym = instrument.zerodha_index_symbol or f"NSE:{instrument.index_name}"
        try:
            data = await self._auth_get("/quote/ltp", params={"i": sym})
            return float((data.get(sym) or {}).get("last_price") or 0.0)
        except Exception:
            return 0.0

    async def get_spot_price(self, instrument: InstrumentMeta) -> float:
        return await self.get_index_price(instrument)

    async def get_perp_price(self, instrument: InstrumentMeta) -> float:
        return await self.get_index_price(instrument)

    async def get_candles(
        self,
        instrument: InstrumentMeta,
        resolution: str,
        limit: int = 200,
    ) -> List[Candle]:
        token = instrument.zerodha_token
        if not token:
            log.warning("No zerodha_token for %s — cannot fetch candles", instrument.underlying)
            return []

        want_4h = resolution == "4H"
        interval = _RESOLUTION_MAP.get(resolution, "60minute")

        # Compute date range — Zerodha requires from/to as dates
        now = datetime.now(timezone(timedelta(hours=5, minutes=30)))  # IST
        n_bars = limit * 4 if want_4h else limit
        # 60min: ~1 bar/hr trading hours; use calendar days with buffer
        days_needed = max(2, int(n_bars / 6) + 5)
        from_dt = now - timedelta(days=days_needed)
        from_str = from_dt.strftime("%Y-%m-%d %H:%M:%S")
        to_str = now.strftime("%Y-%m-%d %H:%M:%S")

        try:
            data = await self._auth_get(
                f"/instruments/historical/{token}/{interval}",
                params={"from": from_str, "to": to_str, "continuous": 0},
            )
            raw = data.get("candles", [])
        except Exception as exc:
            log.error("Zerodha candle fetch failed for %s: %s", instrument.underlying, exc)
            return []

        candles: List[Candle] = []
        for row in raw:
            try:
                # [timestamp_str, open, high, low, close, volume, oi]
                candles.append(Candle(
                    timestamp_ms=_parse_kite_ts(str(row[0])),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]) if len(row) > 5 else 0.0,
                ))
            except (IndexError, ValueError, TypeError):
                continue

        # Sort ascending
        candles.sort(key=lambda c: c.timestamp_ms)

        if want_4h:
            candles = _aggregate_4h(candles)

        return candles[-limit:]

    async def get_option_chain(self, instrument: InstrumentMeta) -> List[OptionSummary]:
        # NFO option chain requires fetching instruments CSV and pricing — complex flow
        # Returning empty until full NFO integration is implemented
        log.info("Zerodha option chain not yet implemented for %s", instrument.underlying)
        return []

    async def get_dvol(self, instrument: InstrumentMeta) -> Optional[float]:
        """India VIX as DVOL proxy for NIFTY/BANKNIFTY."""
        vix_token = instrument.zerodha_vix_token or _INDIA_VIX_TOKEN
        try:
            data = await self._auth_get(
                f"/quote/ltp", params={"i": f"NSE:INDIA VIX"}
            )
            vix = (data.get("NSE:INDIA VIX") or {}).get("last_price")
            return float(vix) if vix else None
        except Exception:
            return None

    async def get_dvol_history(self, instrument: InstrumentMeta, days: int = 30) -> List[float]:
        """India VIX daily history for IVR computation."""
        vix_token = instrument.zerodha_vix_token or _INDIA_VIX_TOKEN
        now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        from_dt = now - timedelta(days=days + 5)
        try:
            data = await self._auth_get(
                f"/instruments/historical/{vix_token}/day",
                params={
                    "from": from_dt.strftime("%Y-%m-%d"),
                    "to": now.strftime("%Y-%m-%d"),
                    "continuous": 0,
                },
            )
            return [float(row[4]) for row in data.get("candles", []) if len(row) >= 5]
        except Exception:
            return []

    # ─── AuthenticatedExchangeAdapter ──────────────────────────────────────

    async def test_connection(self) -> bool:
        if self._is_paper:
            return True
        try:
            await self._auth_get("/user/profile")
            return True
        except Exception:
            return False

    async def get_balances(self) -> List[AssetBalance]:
        if self._is_paper:
            return _paper_balances()
        data = await self._auth_get("/user/margins")
        balances = []
        for seg, info in (data or {}).items():
            try:
                balances.append(AssetBalance(
                    asset=f"INR ({seg})",
                    available=float(info.get("available", {}).get("live_balance") or 0.0),
                    locked=float(info.get("utilised", {}).get("debits") or 0.0),
                    total=float(info.get("net") or 0.0),
                    usd_value=None,
                ))
            except (TypeError, ValueError):
                continue
        return balances

    async def get_positions(self) -> List[AccountPosition]:
        if self._is_paper:
            return []
        data = await self._auth_get("/portfolio/positions")
        positions = []
        for p in (data.get("net") or []):
            try:
                qty = int(p.get("quantity") or 0)
                if qty == 0:
                    continue
                pnl = float(p.get("pnl") or 0.0)
                positions.append(AccountPosition(
                    symbol=str(p.get("tradingsymbol") or ""),
                    underlying=str(p.get("exchange") or "") + ":" + str(p.get("tradingsymbol", "")[:6]),
                    size=float(qty),
                    side="long" if qty > 0 else "short",
                    entry_price=float(p.get("average_price") or 0.0),
                    mark_price=float(p.get("last_price") or 0.0),
                    unrealized_pnl=pnl,
                    realized_pnl=float(p.get("realised") or 0.0),
                    margin=float(p.get("value") or 0.0),
                    leverage=None,
                    position_type=str(p.get("product") or "MIS"),
                    created_at_ms=None,
                ))
            except (TypeError, ValueError):
                continue
        return positions

    async def get_open_orders(self, underlying: Optional[str] = None) -> List[AccountOrder]:
        if self._is_paper:
            return []
        data = await self._auth_get("/orders")
        orders = []
        for o in (data or []):
            try:
                if o.get("status") not in ("OPEN", "TRIGGER PENDING"):
                    continue
                orders.append(AccountOrder(
                    order_id=str(o.get("order_id") or ""),
                    symbol=str(o.get("tradingsymbol") or ""),
                    side="buy" if o.get("transaction_type") == "BUY" else "sell",
                    size=float(o.get("quantity") or 0.0),
                    price=float(o.get("price") or 0.0),
                    filled_size=float(o.get("filled_quantity") or 0.0),
                    status=str(o.get("status") or "open").lower(),
                    order_type=str(o.get("order_type") or "LIMIT").lower(),
                    created_at_ms=_parse_kite_ts(o.get("order_timestamp")),
                ))
            except (TypeError, ValueError):
                continue
        return orders

    async def get_fills(self, limit: int = 50) -> List[AccountFill]:
        if self._is_paper:
            return []
        data = await self._auth_get("/trades")
        fills = []
        for f in (data or [])[:limit]:
            try:
                fills.append(AccountFill(
                    fill_id=str(f.get("trade_id") or ""),
                    order_id=str(f.get("order_id") or ""),
                    symbol=str(f.get("tradingsymbol") or ""),
                    side="buy" if f.get("transaction_type") == "BUY" else "sell",
                    size=float(f.get("quantity") or 0.0),
                    price=float(f.get("average_price") or 0.0),
                    fee=0.0,
                    fee_asset="INR",
                    pnl=0.0,
                    created_at_ms=_parse_kite_ts(f.get("fill_timestamp")),
                ))
            except (TypeError, ValueError):
                continue
        return fills

    async def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        balances = await self.get_balances()
        positions = await self.get_positions()
        orders = await self.get_open_orders()

        total_bal = sum(b.total for b in balances)
        unreal_pnl = sum(p.unrealized_pnl for p in positions)
        real_pnl = sum(p.realized_pnl for p in positions)
        margin_used = sum(abs(p.margin) for p in positions)

        return PortfolioSnapshot(
            exchange="zerodha",
            display_name="Zerodha Kite",
            total_balance_usd=round(total_bal, 2),
            unrealized_pnl_usd=round(unreal_pnl, 2),
            realized_pnl_usd=round(real_pnl, 2),
            margin_used=round(margin_used, 2),
            margin_available=max(0.0, round(total_bal - margin_used, 2)),
            positions_count=len(positions),
            open_orders_count=len(orders),
            balances=balances,
            timestamp_ms=int(time.time() * 1000),
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _parse_kite_ts(ts_str) -> int:
    """Parse Zerodha timestamp string '2024-01-15 10:30:00' → ms."""
    if not ts_str:
        return int(time.time() * 1000)
    try:
        dt = datetime.strptime(str(ts_str), "%Y-%m-%d %H:%M:%S")
        return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
    except Exception:
        return int(time.time() * 1000)


def _paper_balances() -> List[AssetBalance]:
    return [
        AssetBalance(asset="INR (equity)", available=500000.0, locked=50000.0, total=550000.0, usd_value=None),
        AssetBalance(asset="INR (commodity)", available=100000.0, locked=0.0, total=100000.0, usd_value=None),
    ]
