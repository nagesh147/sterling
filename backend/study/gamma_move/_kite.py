"""Shared Kite plumbing for the Gamma Move calibration studies.

Minimum-spacing pacing, not a token bucket: Kite's historical endpoint allows
~3 rq/s and a bucket with burst allowance empties itself in the first second and
then eats 429s for the rest of the cycle.
"""
from __future__ import annotations

import asyncio, sys, time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

IST_OFFSET_H = 5.5


class Pacer:
    def __init__(self, rate: float = 2.8):
        self._gap = 1.0 / rate
        self._next = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            if now < self._next:
                await asyncio.sleep(self._next - now)
                now = time.monotonic()
            self._next = now + self._gap


async def client():
    from app.services import db
    db.init()
    from app.services.exchanges.kite import accounts
    accounts._loaded = False
    accounts.bootstrap()
    acct = accounts.get_active("default")
    if not acct:
        raise SystemExit("no active Kite account")
    return await accounts.acquire_client(acct)


async def candles(c, pacer, token, interval, frm, to, oi=True, retries=3):
    """`[{date, open, high, low, close, volume, oi}]`, or [] on failure."""
    for attempt in range(retries):
        await pacer.wait()
        try:
            raw = await c.get_historical(int(token), interval, frm, to, False, oi)
        except Exception as exc:                                  # noqa: BLE001
            if attempt == retries - 1:
                return []
            await asyncio.sleep(0.8 * (attempt + 1))
            continue
        rows = (raw or {}).get("candles") if isinstance(raw, dict) else raw
        return rows or []
    return []


def norm(rows):
    """Kite returns positional arrays; name the columns once, here."""
    out = []
    for r in rows or []:
        if isinstance(r, dict):
            out.append(r)
        elif len(r) >= 7:
            out.append({"date": r[0], "open": r[1], "high": r[2], "low": r[3],
                        "close": r[4], "volume": r[5], "oi": r[6]})
        elif len(r) >= 6:
            out.append({"date": r[0], "open": r[1], "high": r[2], "low": r[3],
                        "close": r[4], "volume": r[5], "oi": 0})
    return out


def pct(values, q):
    if not values:
        return float("nan")
    s = sorted(values)
    i = min(len(s) - 1, max(0, int(round(q / 100.0 * (len(s) - 1)))))
    return s[i]
