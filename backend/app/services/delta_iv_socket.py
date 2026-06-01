"""Real-time options IV/Greeks stream from Delta Exchange India.

Subscribes to the `mark_price` channel (per Asset-Expiry, e.g. ``BTC-270625``) for
every listed option chain within ``MAX_DTE`` and keeps the latest per-strike
IV/Greeks in memory. Mirrors ``delta_l2_socket.DeltaL2Manager`` but is **start-gated**:
importing this module never opens a socket — ``iv_manager.start()`` is called from the
FastAPI lifespan only when ``STERLING_IV_STREAM=1``.

Component ① of the realtime-iv-stream design
(docs/superpowers/specs/2026-06-01-realtime-iv-stream-design.md).
"""
import asyncio
import datetime as dt
import json
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx
import websockets

log = logging.getLogger(__name__)

_BASE = "https://api.india.delta.exchange"
_WS = "wss://socket.india.delta.exchange"
MAX_DTE = 45


@dataclass(frozen=True)
class ParsedSym:
    option_type: str   # "call" | "put"
    underlying: str
    strike: float
    expiry: str        # "DDMMYY"


def _parse_symbol(symbol: str) -> Optional[ParsedSym]:
    if not symbol:
        return None
    s = symbol.split(":", 1)[1] if symbol.startswith("MARK:") else symbol
    parts = s.split("-")
    if len(parts) != 4 or parts[0] not in ("C", "P"):
        return None
    try:
        return ParsedSym(
            "call" if parts[0] == "C" else "put",
            parts[1],
            float(parts[2]),
            parts[3],
        )
    except (ValueError, IndexError):
        return None


def _dte(expiry_ddmmyy: str, today: Optional[dt.date] = None) -> int:
    today = today or dt.datetime.utcnow().date()
    try:
        d = int(expiry_ddmmyy[0:2])
        m = int(expiry_ddmmyy[2:4])
        y = 2000 + int(expiry_ddmmyy[4:6])
        return (dt.date(y, m, d) - today).days
    except (ValueError, IndexError):
        return -1


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _subs_from_products(products: list, max_dte: int, today: Optional[dt.date] = None) -> List[str]:
    subs = set()
    for p in products:
        parsed = _parse_symbol(str(p.get("symbol", "")))
        if parsed is None:
            continue
        d = _dte(parsed.expiry, today)
        if 0 <= d <= max_dte:
            subs.add(f"{parsed.underlying}-{parsed.expiry}")
    return sorted(subs)


async def _fetch_option_products() -> list:
    """Page all live option products from Delta India public REST."""
    out: list = []
    params = {"contract_types": "call_options,put_options", "page_size": 200}
    async with httpx.AsyncClient(base_url=_BASE, timeout=10.0) as c:
        after = None
        for _ in range(50):  # hard page cap
            q = dict(params)
            if after:
                q["after"] = after
            r = await c.get("/v2/products", params=q)
            r.raise_for_status()
            body = r.json()
            out.extend(body.get("result") or [])
            after = (body.get("meta") or {}).get("after")
            if not after:
                break
    return out


@dataclass
class IVTick:
    option_symbol: str
    underlying: str
    option_type: str
    strike: float
    expiry: str
    dte: int
    mark_iv: float
    bid_iv: float
    ask_iv: float
    mark_price: float
    best_bid: float
    best_ask: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float
    ts_exchange: float
    ts_local: float


class DeltaIVManager:
    def __init__(self, today: Optional[dt.date] = None, max_dte: int = MAX_DTE):
        self.ticks: Dict[str, IVTick] = {}
        self._last_update: Dict[str, float] = {}
        self._subs: List[str] = []
        self._today = today
        self.max_dte = max_dte
        self._running = False
        self._task = None

    # ---- ingest -------------------------------------------------------
    def _handle_message(self, data: dict) -> None:
        if not isinstance(data, dict) or data.get("type") != "mark_price":
            return
        raw = str(data.get("symbol", ""))
        parsed = _parse_symbol(raw)
        if parsed is None:
            return
        sym = raw.split(":", 1)[1] if raw.startswith("MARK:") else raw
        now = time.time()
        tick = IVTick(
            option_symbol=sym, underlying=parsed.underlying, option_type=parsed.option_type,
            strike=parsed.strike, expiry=parsed.expiry, dte=_dte(parsed.expiry, self._today),
            mark_iv=_f(data.get("implied_volatility")), bid_iv=_f(data.get("bid_iv")),
            ask_iv=_f(data.get("ask_iv")), mark_price=_f(data.get("price")),
            best_bid=_f(data.get("best_bid")), best_ask=_f(data.get("best_ask")),
            delta=_f(data.get("delta")), gamma=_f(data.get("gamma")), theta=_f(data.get("theta")),
            vega=_f(data.get("vega")), rho=_f(data.get("rho")),
            ts_exchange=_f(data.get("timestamp")) / 1e6, ts_local=now,
        )
        self.ticks[sym] = tick
        self._last_update[parsed.underlying] = now

    # ---- read API -----------------------------------------------------
    def get(self, option_symbol: str) -> Optional[IVTick]:
        return self.ticks.get(option_symbol)

    def chain(self, underlying: str) -> List[IVTick]:
        u = underlying.upper()
        return [t for t in self.ticks.values() if t.underlying == u]

    def last_update_ts(self, underlying: str) -> Optional[float]:
        return self._last_update.get(underlying.upper())

    def atm_iv(self, underlying: str, dte: int, spot: float) -> Optional[float]:
        cohort = [t for t in self.chain(underlying) if t.mark_iv > 0]
        if not cohort:
            return None
        target_dte = min({t.dte for t in cohort}, key=lambda d: abs(d - dte))
        same_exp = [t for t in cohort if t.dte == target_dte]
        best = min(same_exp, key=lambda t: abs(t.strike - spot))
        return best.mark_iv

    def is_fresh(self, underlying: str, max_age_s: float = 10.0) -> bool:
        ts = self._last_update.get(underlying.upper())
        return ts is not None and (time.time() - ts) <= max_age_s

    # ---- discovery + socket ------------------------------------------
    async def discover_subscriptions(self) -> List[str]:
        try:
            products = await _fetch_option_products()
            self._subs = _subs_from_products(products, self.max_dte, self._today)
        except Exception as e:  # keep last-known subs on failure
            log.warning("IV discover failed, keeping %d subs: %s", len(self._subs), e)
        return self._subs

    async def _listen(self) -> None:
        while self._running:
            try:
                await self.discover_subscriptions()
                if not self._subs:
                    log.warning("IV stream: no option subscriptions discovered; retrying")
                    await asyncio.sleep(30)
                    continue
                async with websockets.connect(_WS, ping_interval=20) as ws:
                    await ws.send(json.dumps({
                        "type": "subscribe",
                        "payload": {"channels": [{"name": "mark_price", "symbols": self._subs}]},
                    }))
                    log.info("IV stream subscribed to %d expiries", len(self._subs))
                    last_refresh = time.time()
                    while self._running:
                        msg = await asyncio.wait_for(ws.recv(), timeout=60)
                        self._handle_message(json.loads(msg))
                        if time.time() - last_refresh > 3600:
                            new = await self.discover_subscriptions()
                            await ws.send(json.dumps({
                                "type": "subscribe",
                                "payload": {"channels": [{"name": "mark_price", "symbols": new}]},
                            }))
                            last_refresh = time.time()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("Delta IV socket error: %s", e)
                await asyncio.sleep(5)

    def start(self) -> None:
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._listen())

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()


# module singleton — NOT auto-started (started by FastAPI lifespan when STERLING_IV_STREAM=1)
iv_manager = DeltaIVManager()
