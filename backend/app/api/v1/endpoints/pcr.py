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
_CACHE_S = 20.0
_NEXT = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>')


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _hhmm(time_s: str) -> str:
    if "T" in time_s and len(time_s) >= 16:
        return time_s[11:16]
    return time_s[:5]


def _marks(ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by = {_hhmm(t["time"]): t for t in ticks if t.get("time")}
    out = []
    for hhmm in SLOT_HHMM:
        hit = by.get(hhmm)
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
    last = ticks[-1]
    return {
        "hhmm": _hhmm(last["time"]),
        "pcr": last["pcr"],
        "volumePcr": last["volumePcr"],
        "changeOiPcr": last["changeOiPcr"],
        "indexClose": last["indexClose"],
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
        ticks.append({
            "time": t,
            "pcr": _num(row.get("pcr")),
            "volumePcr": _num(row.get("volume_pcr")),
            "changeOiPcr": _num(row.get("change_oi_pcr")),
            "indexClose": _num(row.get("index_close")),
            "expiry": str(row.get("expiry_date") or "")[:10],
        })
    if not ticks:
        return None
    spot = page.get("initialSpot") or {}
    expiry = str(page.get("initialExpiry") or ticks[0].get("expiry") or "")[:10]
    live = page.get("initialPcr")
    return {
        "id": symbol,
        "expiry": expiry,
        "livePcr": _num(live) if live is not None else ticks[-1]["pcr"],
        "spot": {
            "ltp": spot.get("last_trade_price"),
            "changePer": spot.get("change_per"),
            "maxPain": spot.get("max_pain"),
            "vix": spot.get("vix_value"),
            "timestamp": spot.get("timestamp"),
        },
        "marks": _marks(ticks),
        "latest": _latest(ticks),
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
        if isinstance(result, dict) and result.get("marks"):
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
