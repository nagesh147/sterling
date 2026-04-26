"""
OKX public data adapter.
Uses only public endpoints — no API key required.
Candles, index price, perp price, option chain (tickers + opt-summary merged).
"""
import time
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from app.services.exchanges.base import BaseExchangeAdapter
from app.schemas.market import Candle, OptionSummary
from app.schemas.instruments import InstrumentMeta
from app.core.logging import get_logger

log = get_logger(__name__)

_OKX_BASE = "https://www.okx.com"

_RESOLUTION_MAP = {
    "15m": "15m",
    "1H": "1H",
    "4H": "4H",
}


def _normalize_ts_ms(ts: int | float) -> int:
    ts = int(ts)
    if ts < 1_000_000_000_000:
        return ts * 1000
    if ts < 1_000_000_000_000_000:
        return ts
    if ts < 1_000_000_000_000_000_000:
        return ts // 1000
    return ts // 1_000_000


def _okx_expiry_str(inst_id: str) -> str:
    """Extract YYMMDD from OKX instId like BTC-USD-241227-100000-C."""
    try:
        return inst_id.split("-")[2]
    except IndexError:
        return "UNKNOWN"


def _okx_dte(expiry_str: str) -> int:
    try:
        dt = datetime.strptime(expiry_str, "%y%m%d").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0, (dt - now).days)
    except Exception:
        return -1


def _okx_option_type(inst_id: str) -> str:
    return "call" if inst_id.endswith("-C") else "put"


def _okx_strike(inst_id: str) -> Optional[float]:
    try:
        return float(inst_id.split("-")[3])
    except (IndexError, ValueError):
        return None


class OKXAdapter(BaseExchangeAdapter):
    def __init__(self, base_url: str = _OKX_BASE, timeout: float = 10.0) -> None:
        self._base = base_url
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

    async def _get(self, path: str, params: dict) -> dict | list:
        client = await self._client_get()
        resp = await client.get(path, params=params)
        resp.raise_for_status()
        body = resp.json()
        code = body.get("code", "0")
        if code != "0":
            raise RuntimeError(f"OKX error {code}: {body.get('msg')}")
        return body.get("data", body)

    async def ping(self) -> bool:
        try:
            await self._get("/api/v5/public/time", {})
            return True
        except Exception:
            return False

    async def get_index_price(self, instrument: InstrumentMeta) -> float:
        index_id = instrument.okx_index_id or f"{instrument.underlying}-USDT"
        data = await self._get("/api/v5/market/index-tickers", {"instId": index_id})
        if isinstance(data, list) and data:
            return float(data[0]["idxPx"])
        raise RuntimeError(f"No index price for {index_id}")

    async def get_spot_price(self, instrument: InstrumentMeta) -> float:
        return await self.get_index_price(instrument)

    async def get_perp_price(self, instrument: InstrumentMeta) -> float:
        perp = instrument.okx_perp_symbol or f"{instrument.underlying}-USDT-SWAP"
        data = await self._get("/api/v5/market/ticker", {"instId": perp})
        if isinstance(data, list) and data:
            return float(data[0]["last"])
        raise RuntimeError(f"No perp price for {perp}")

    async def get_candles(
        self,
        instrument: InstrumentMeta,
        resolution: str,
        limit: int = 200,
    ) -> List[Candle]:
        bar = _RESOLUTION_MAP.get(resolution)
        if not bar:
            raise ValueError(f"Unsupported resolution: {resolution}")

        perp = instrument.okx_perp_symbol or f"{instrument.underlying}-USDT-SWAP"
        data = await self._get(
            "/api/v5/market/candles",
            {"instId": perp, "bar": bar, "limit": str(min(limit, 300))},
        )

        candles: List[Candle] = []
        if isinstance(data, list):
            for row in data:
                try:
                    # row: [ts, open, high, low, close, vol, volCcy, volCcyQuote, confirm]
                    ts = _normalize_ts_ms(int(row[0]))
                    candles.append(Candle(
                        timestamp_ms=ts,
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                    ))
                except (IndexError, ValueError, TypeError):
                    continue

        # OKX returns newest first — reverse for chronological order
        return list(reversed(candles))

    async def get_option_chain(self, instrument: InstrumentMeta) -> List[OptionSummary]:
        if not instrument.has_options or not instrument.okx_underlying:
            return []

        ul = instrument.okx_underlying
        now_ms = int(time.time() * 1000)

        try:
            tickers_data = await self._get(
                "/api/v5/market/tickers",
                {"instType": "OPTION", "uly": ul},
            )
        except Exception as exc:
            log.error("OKX tickers fetch failed for %s: %s", ul, exc)
            return []

        try:
            summary_data = await self._get(
                "/api/v5/market/opt-summary",
                {"uly": ul},
            )
        except Exception as exc:
            log.warning("OKX opt-summary fetch failed: %s", exc)
            summary_data = []

        # Build summary lookup by instId
        summary_by_id: dict = {}
        if isinstance(summary_data, list):
            for s in summary_data:
                iid = s.get("instId", "")
                if iid:
                    summary_by_id[iid] = s

        options: List[OptionSummary] = []
        if not isinstance(tickers_data, list):
            return options

        for t in tickers_data:
            inst_id: str = t.get("instId", "")
            parts = inst_id.split("-")
            if len(parts) != 5:
                continue

            expiry_str = _okx_expiry_str(inst_id)
            dte = _okx_dte(expiry_str)
            if dte < 0:
                continue

            strike = _okx_strike(inst_id)
            if strike is None:
                continue

            opt_type = _okx_option_type(inst_id)
            try:
                bid = float(t.get("bidPx") or 0.0)
                ask = float(t.get("askPx") or 0.0)
                last = float(t.get("last") or 0.0)
                vol = float(t.get("vol24h") or 0.0)
                ts_raw = t.get("ts") or now_ms

                smry = summary_by_id.get(inst_id, {})
                iv = float(smry.get("markVol") or 0.0)
                delta = float(smry.get("delta") or 0.0)
                mark = float(smry.get("fwdPx") or last or (bid + ask) / 2)
                mid = (bid + ask) / 2 if bid > 0 and ask > 0 else mark

                # OKX OI: not in tickers/opt-summary, set to 0 and let health engine filter
                oi = 0.0

                options.append(OptionSummary(
                    instrument_name=inst_id,
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
                ))
            except (ValueError, TypeError, KeyError):
                continue

        return options

    async def get_dvol(self, instrument: InstrumentMeta) -> Optional[float]:
        # OKX has no direct DVOL index equivalent — return None
        return None

    async def get_dvol_history(
        self, instrument: InstrumentMeta, days: int = 30
    ) -> List[float]:
        return []

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
