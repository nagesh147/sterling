"""Intraday + weekly Put-Call Ratio — public market data, no session."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import httpx
from fastapi import APIRouter

router = APIRouter(prefix="/pcr", tags=["pcr"])

PAGES = {
    "NIFTY": "https://www.niftytrader.in/nifty-put-call-ratio",
    "BANKNIFTY": "https://www.niftytrader.in/banknifty-put-call-ratio",
    "FINNIFTY": "https://www.niftytrader.in/finnifty-put-call-ratio",
    "SENSEX": "https://www.niftytrader.in/sensex-put-call-ratio",
    "MIDCPNIFTY": "https://www.niftytrader.in/midcpnifty-put-call-ratio",
}

SLOT_HHMM = [
    f"{h:02d}:{m:02d}"
    for h, m in (
        (9, 15), (9, 30), (9, 45),
        (10, 0), (10, 15), (10, 30), (10, 45),
        (11, 0), (11, 15), (11, 30), (11, 45),
        (12, 0), (12, 15), (12, 30), (12, 45),
        (13, 0), (13, 15), (13, 30), (13, 45),
        (14, 0), (14, 15), (14, 30), (14, 45),
        (15, 0), (15, 15), (15, 30),
    )
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json",
    "Referer": "https://www.niftytrader.in/",
}

_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_CACHE_S = 8.0
_NEXT = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')


def _num(v: Any) -> float | None:
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    return n


def _hhmm(time_s: str) -> str:
    if "T" in time_s and len(time_s) >= 16:
        return time_s[11:16]
    return time_s[:5]


def _mins(hhmm: str) -> int:
    try:
        return int(hhmm[:2]) * 60 + int(hhmm[3:5])
    except (TypeError, ValueError):
        return -1


def _marks(ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Last print in each 15-minute bucket.

    NiftyTrader now emits ~1-minute rows (09:10, 09:11, …) instead of only the
    15-minute clock. Matching the clock exactly dropped every row on those
    days, the session looked empty, and the desk froze on yesterday's close.
    """
    ordered = sorted(ticks, key=lambda t: str(t.get("time") or ""))
    out: list[dict[str, Any]] = []
    for i, hhmm in enumerate(SLOT_HHMM):
        end = _mins(hhmm)
        start = 9 * 60 + 10 if i == 0 else _mins(SLOT_HHMM[i - 1]) + 1
        hit = None
        for t in ordered:
            m = _mins(_hhmm(str(t.get("time") or "")))
            if start <= m <= end:
                hit = t
        if not hit:
            continue
        out.append({
            "hhmm": hhmm,
            "pcr": hit["pcr"],
            "volumePcr": hit["volumePcr"],
            "changeOiPcr": hit["changeOiPcr"],
            "indexClose": hit["indexClose"],
        })
    return out


def _latest(ticks: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not ticks:
        return None
    last = max(ticks, key=lambda t: str(t.get("time") or ""))
    return {
        "hhmm": _hhmm(str(last["time"])),
        "pcr": last["pcr"],
        "volumePcr": last["volumePcr"],
        "changeOiPcr": last["changeOiPcr"],
        "indexClose": last["indexClose"],
    }


def _spot(page: dict[str, Any], latest: dict[str, Any] | None) -> dict[str, Any]:
    spot = page.get("initialSpot") or {}
    ltp = _num(spot.get("last_trade_price"))
    if ltp is None:
        ltp = _num(spot.get("ltp"))
    if ltp is None and latest is not None:
        ltp = _num(latest.get("indexClose"))
    chg = _num(spot.get("change_per"))
    if chg is None:
        close = _num(spot.get("close"))
        if ltp is not None and close not in (None, 0):
            chg = round((ltp - close) / close * 100, 2)
    ts = spot.get("timestamp") or spot.get("created_at")
    return {
        "ltp": ltp,
        "changePer": chg,
        "maxPain": _num(spot.get("max_pain")),
        "vix": _num(spot.get("vix_value")),
        "timestamp": ts,
    }


async def _scrape(client: httpx.AsyncClient, symbol: str, url: str) -> dict[str, Any] | None:
    import json
    try:
        res = await client.get(url, headers=HEADERS)
        res.raise_for_status()
    except Exception:
        return None
    m = _NEXT.search(res.text)
    if not m:
        return None
    try:
        page = json.loads(m.group(1)).get("props", {}).get("pageProps", {})
    except Exception:
        return None
    raw = page.get("initialPcrData") or []
    ticks = []
    for row in raw:
        t = str(row.get("time") or "")
        if not t:
            continue
        pcr = _num(row.get("pcr"))
        if pcr is None:
            continue
        ticks.append({
            "time": t,
            "pcr": pcr,
            "volumePcr": _num(row.get("volume_pcr")) or 0.0,
            "changeOiPcr": _num(row.get("change_oi_pcr")) or 0.0,
            "indexClose": _num(row.get("index_close")) or 0.0,
            "expiry": str(row.get("expiry_date") or "")[:10],
        })
    latest = _latest(ticks)
    marks = _marks(ticks)
    if not ticks and page.get("initialPcr") is None:
        return None
    live = _num(page.get("initialPcr"))
    if live is None and latest is not None:
        live = latest["pcr"]
    expiry = str(page.get("initialExpiry") or (ticks[0].get("expiry") if ticks else "") or "")[:10]
    return {
        "id": symbol,
        "expiry": expiry,
        "livePcr": live,
        "spot": _spot(page, latest),
        "marks": marks,
        "latest": latest,
    }


@router.get("/session")
async def pcr_session() -> dict[str, Any]:
    now = time.time()
    cached = _CACHE.get("payload")
    if cached and now - float(_CACHE["at"]) < _CACHE_S:
        return cached
    series: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=12.0) as client:
        results = await asyncio.gather(
            *[_scrape(client, sym, url) for sym, url in PAGES.items()],
            return_exceptions=True,
        )
    live = 0
    for (sym, _), result in zip(PAGES.items(), results):
        if isinstance(result, dict) and (result.get("marks") or result.get("latest") or result.get("livePcr") is not None):
            series[sym] = result
            live += 1
    payload = {
        "asOf": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "live" if live else "snapshot",
        "series": series,
    }
    if live:
        _CACHE["at"] = now
        _CACHE["payload"] = payload
    return payload
