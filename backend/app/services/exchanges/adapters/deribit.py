import time
import httpx
from typing import List, Optional
from datetime import datetime, timezone, timedelta

from app.services.exchanges.base import BaseExchangeAdapter
from app.schemas.market import Candle, OptionSummary
from app.schemas.instruments import InstrumentMeta
from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

_RESOLUTION_MAP = {"15m": 15, "1H": 60, "4H": 240}


def _normalize_ts_ms(ts: int | float) -> int:
    """Normalize timestamp to milliseconds. Handles sec/ms/us/ns input."""
    ts = int(ts)
    if ts < 1_000_000_000_000:           # seconds
        return ts * 1000
    if ts < 1_000_000_000_000_000:       # milliseconds
        return ts
    if ts < 1_000_000_000_000_000_000:   # microseconds
        return ts // 1000
    return ts // 1_000_000               # nanoseconds


def _parse_expiry_date(instrument_name: str) -> str:
    """Extract date string from Deribit instrument name like BTC-27DEC24-100000-C."""
    try:
        parts = instrument_name.split("-")
        return parts[1] if len(parts) >= 2 else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def _compute_dte(expiry_str: str) -> int:
    """Compute days to expiry from Deribit date string like '27DEC24'."""
    try:
        dt = datetime.strptime(expiry_str, "%d%b%y").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = dt - now
        return max(0, delta.days)
    except Exception:
        return -1


class DeribitAdapter(BaseExchangeAdapter):
    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0):
        self._base = base_url or settings.deribit_base_url
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _client_get(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base,
                timeout=self._timeout,
                headers={"User-Agent": "Sterling/1.0"},
            )
        return self._client

    async def _get(self, path: str, params: dict) -> dict:
        client = await self._client_get()
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise RuntimeError(f"Deribit error: {body['error']}")
        return body.get("result", body)

    async def ping(self) -> bool:
        try:
            await self._get("/public/test", {})
            return True
        except Exception:
            return False

    async def get_index_price(self, instrument: InstrumentMeta) -> float:
        result = await self._get(
            "/public/get_index_price",
            {"index_name": instrument.index_name},
        )
        return float(result["index_price"])

    async def get_spot_price(self, instrument: InstrumentMeta) -> float:
        return await self.get_index_price(instrument)

    async def get_perp_price(self, instrument: InstrumentMeta) -> float:
        result = await self._get(
            "/public/ticker",
            {"instrument_name": instrument.perp_symbol},
        )
        return float(result["last_price"])

    async def get_candles(
        self,
        instrument: InstrumentMeta,
        resolution: str,
        limit: int = 200,
    ) -> List[Candle]:
        res_min = _RESOLUTION_MAP.get(resolution)
        if res_min is None:
            raise ValueError(f"Unsupported resolution: {resolution}")

        now_ms = int(time.time() * 1000)
        start_ms = now_ms - limit * res_min * 60 * 1000

        result = await self._get(
            "/public/get_tradingview_chart_data",
            {
                "instrument_name": instrument.perp_symbol,
                "start_timestamp": start_ms,
                "end_timestamp": now_ms,
                "resolution": str(res_min),
            },
        )

        ticks = result.get("ticks", [])
        opens = result.get("open", [])
        highs = result.get("high", [])
        lows = result.get("low", [])
        closes = result.get("close", [])
        volumes = result.get("volume", [])

        candles = []
        for i, ts in enumerate(ticks):
            try:
                candles.append(
                    Candle(
                        timestamp_ms=_normalize_ts_ms(ts),
                        open=float(opens[i]),
                        high=float(highs[i]),
                        low=float(lows[i]),
                        close=float(closes[i]),
                        volume=float(volumes[i]) if i < len(volumes) else 0.0,
                    )
                )
            except (IndexError, ValueError, TypeError):
                continue

        return sorted(candles, key=lambda c: c.timestamp_ms)

    async def get_option_chain(
        self, instrument: InstrumentMeta
    ) -> List[OptionSummary]:
        if not instrument.has_options:
            return []

        summaries = await self._get(
            "/public/get_book_summary_by_currency",
            {"currency": instrument.exchange_currency, "kind": "option"},
        )

        options: List[OptionSummary] = []
        now_ms = int(time.time() * 1000)

        for s in summaries:
            name: str = s.get("instrument_name", "")
            parts = name.split("-")
            if len(parts) != 4:
                continue

            expiry_str = parts[1]
            dte = _compute_dte(expiry_str)
            if dte < 0:
                continue

            try:
                strike = float(parts[2])
                opt_type = "call" if parts[3].upper() == "C" else "put"
                bid = float(s.get("bid_price") or 0.0)
                ask = float(s.get("ask_price") or 0.0)
                mark = float(s.get("mark_price") or 0.0)
                mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else mark
                iv = float(s.get("mark_iv") or 0.0)
                delta = float(s.get("delta") or 0.0)
                oi = float(s.get("open_interest") or 0.0)
                vol = float(s.get("volume") or 0.0)
                ts_raw = s.get("creation_timestamp") or now_ms

                options.append(
                    OptionSummary(
                        instrument_name=name,
                        underlying=instrument.underlying,
                        strike=strike,
                        expiry_date=expiry_str,
                        dte=dte,
                        option_type=opt_type,
                        bid=bid,
                        ask=ask,
                        mark_price=mark,
                        mid_price=mid,
                        mark_iv=iv,
                        delta=delta,
                        open_interest=oi,
                        volume_24h=vol,
                        last_updated_ms=_normalize_ts_ms(ts_raw),
                    )
                )
            except (ValueError, TypeError, KeyError):
                continue

        return options

    async def get_dvol(self, instrument: InstrumentMeta) -> Optional[float]:
        if not instrument.dvol_symbol:
            return None
        try:
            result = await self._get(
                "/public/ticker",
                {"instrument_name": instrument.dvol_symbol},
            )
            return float(result.get("last_price") or result.get("mark_price") or 0.0) or None
        except Exception:
            return None

    async def get_dvol_history(
        self, instrument: InstrumentMeta, days: int = 30
    ) -> List[float]:
        if not instrument.dvol_symbol:
            return []
        try:
            now_ms = int(time.time() * 1000)
            start_ms = now_ms - days * 24 * 60 * 60 * 1000
            result = await self._get(
                "/public/get_tradingview_chart_data",
                {
                    "instrument_name": instrument.dvol_symbol,
                    "start_timestamp": start_ms,
                    "end_timestamp": now_ms,
                    "resolution": "1D",
                },
            )
            closes = result.get("close", [])
            return [float(c) for c in closes if c is not None]
        except Exception:
            return []

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
