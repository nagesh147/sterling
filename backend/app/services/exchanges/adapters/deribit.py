import math
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

# Deribit valid resolutions: 1,3,5,10,15,30,60,120,180,360,720,1D
# 240 NOT valid — 4H fetched as 1H bars and aggregated client-side
_RESOLUTION_MAP = {"15m": 15, "1H": 60, "4H": 60}


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bs_delta(S: float, K: float, T_years: float, sigma: float, opt_type: str) -> float:
    """Black-Scholes delta. sigma as decimal (0.40=40%), T in years.
    Returns +delta for calls (0..1), -delta for puts (-1..0).
    Falls back to 0.0 on bad inputs.
    """
    if T_years <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    try:
        d1 = (math.log(S / K) + 0.5 * sigma ** 2 * T_years) / (sigma * math.sqrt(T_years))
        nd1 = _norm_cdf(d1)
        return nd1 if opt_type == "call" else nd1 - 1.0
    except (ValueError, ZeroDivisionError, OverflowError):
        return 0.0


def _aggregate_4h(candles: List[Candle]) -> List[Candle]:
    """Group 1H candles into 4H buckets (4 bars → 1 bar)."""
    result: List[Candle] = []
    buf: List[Candle] = []
    for c in candles:
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
    # Include partial trailing group (current incomplete 4H candle)
    if buf:
        result.append(Candle(
            timestamp_ms=buf[0].timestamp_ms,
            open=buf[0].open,
            high=max(x.high for x in buf),
            low=min(x.low for x in buf),
            close=buf[-1].close,
            volume=sum(x.volume for x in buf),
        ))
    return result


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

        # 4H: fetch 4× 1H bars then aggregate — Deribit has no resolution=240
        want_4h = resolution == "4H"
        fetch_limit = limit * 4 if want_4h else limit

        now_ms = int(time.time() * 1000)
        start_ms = now_ms - fetch_limit * res_min * 60 * 1000

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

        candles = sorted(candles, key=lambda c: c.timestamp_ms)

        if want_4h:
            candles = _aggregate_4h(candles)

        return candles[-limit:]

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
                # Deribit book_summary has no greeks — compute delta via BS
                spot_s = float(s.get("underlying_price") or 0.0)
                T = max(0.0, dte / 365.0)
                sigma = iv / 100.0 if iv > 0 else 0.0
                if spot_s > 0 and T > 0 and sigma > 0:
                    delta = _bs_delta(spot_s, strike, T, sigma, opt_type)
                else:
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
        """Fetch current DVOL via get_volatility_index_data (latest 1H close)."""
        if not instrument.dvol_symbol:
            return None
        try:
            currency = instrument.dvol_symbol.split("-")[0].upper()
            now_ms = int(time.time() * 1000)
            result = await self._get(
                "/public/get_volatility_index_data",
                {
                    "currency": currency,
                    "start_timestamp": now_ms - 2 * 3600 * 1000,
                    "end_timestamp": now_ms,
                    "resolution": "3600",
                },
            )
            data = result.get("data", [])
            return float(data[-1][4]) if data else None  # [ts, o, h, l, close]
        except Exception:
            return None

    async def get_dvol_history(
        self, instrument: InstrumentMeta, days: int = 30
    ) -> List[float]:
        """Fetch DVOL history via /public/get_volatility_index_data."""
        if not instrument.dvol_symbol:
            return []
        try:
            currency = instrument.dvol_symbol.split("-")[0].upper()  # BTC or ETH
            now_ms = int(time.time() * 1000)
            start_ms = now_ms - days * 24 * 60 * 60 * 1000
            result = await self._get(
                "/public/get_volatility_index_data",
                {
                    "currency": currency,
                    "start_timestamp": start_ms,
                    "end_timestamp": now_ms,
                    "resolution": "86400",  # 1-day in seconds
                },
            )
            # Response: {"data": [[ts, open, high, low, close], ...]}
            data = result.get("data", [])
            return [float(row[4]) for row in data if len(row) >= 5 and row[4] is not None]
        except Exception:
            return []

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
