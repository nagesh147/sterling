"""TrueData realtime tick aggregation for ORB.

Maintains one in-memory minute bucket per subscribed underlying. The strategy
engine consumes completed bars; current ticks are retained separately for
freshness and option quote checks.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
from app.engines.nifty_orb_options import Bar

IST=ZoneInfo("Asia/Kolkata")

@dataclass
class _Bucket:
    start: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class TrueDataOrbRealtime:
    def __init__(self)->None:
        self._buckets: dict[str,_Bucket]={}
        self._latest: dict[str,dict[str,Any]]={}

    def on_tick(self,symbol:str,tick:dict[str,Any])->Bar|None:
        raw=str(tick.get("timestamp") or tick.get("time") or "")
        dt=datetime.fromisoformat(raw.replace("Z","+00:00")) if "T" in raw else datetime.strptime(raw,"%Y-%m-%d %H:%M:%S")
        if dt.tzinfo is None: dt=dt.replace(tzinfo=IST)
        dt=dt.astimezone(IST).replace(second=0,microsecond=0)
        price=float(tick.get("ltp") or 0);volume=float(tick.get("volume") or 0)
        if price<=0:return None
        self._latest[symbol]=dict(tick)
        bucket=self._buckets.get(symbol)
        if bucket is None:
            self._buckets[symbol]=_Bucket(dt,price,price,price,price,volume);return None
        if dt==bucket.start:
            bucket.high=max(bucket.high,price);bucket.low=min(bucket.low,price);bucket.close=price;bucket.volume=max(bucket.volume,volume);return None
        if dt<bucket.start:return None
        completed=Bar(bucket.start,bucket.open,bucket.high,bucket.low,bucket.close,bucket.volume)
        self._buckets[symbol]=_Bucket(dt,price,price,price,price,volume)
        return completed

    def latest_tick(self,symbol:str)->dict[str,Any]|None:return self._latest.get(symbol)
