"""TrueData-native provider for ORB.

Uses TrueData 1-minute history for construction, realtime tick data for quote
freshness, and the documented option-chain endpoint for contract hydration.
The strategy engine remains broker/data-provider agnostic.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any
from app.engines.nifty_orb_options import Bar, OptionContract, StrategyConfig
from app.services.market_data.truedata import TrueDataHistoricalClient
from app.services.nifty_orb_option_chain import normalize_chain, filter_chain

class TrueDataOrbProvider:
    def __init__(self, client: TrueDataHistoricalClient) -> None: self.client=client

    async def bars(self,symbol:str,cfg:StrategyConfig)->list[Bar]:
        rows=await self.client.get_last_bars(symbol,200,interval="1min",bidask=0)
        out=[]
        for r in rows:
            raw=str(r.get("timestamp") or r.get("time") or "")
            dt=datetime.fromisoformat(raw.replace("Z","+00:00")) if "T" in raw else datetime.strptime(raw,"%Y-%m-%d %H:%M:%S")
            out.append(Bar(dt,float(r.get("open",0)),float(r.get("high",0)),float(r.get("low",0)),float(r.get("close",0)),float(r.get("volume",0))))
        return out

    async def latest_tick(self,symbol:str)->dict[str,Any]|None:
        rows=await self.client.get_last_ticks(symbol,1,bidask=1)
        return rows[-1] if rows else None

    async def option_chain(self,symbol:str,expiry:str,cfg:StrategyConfig)->list[OptionContract]:
        payload=await self.client.get_option_chain(symbol,expiry)
        contracts=normalize_chain(payload)
        return filter_chain(contracts,cfg)

    async def symbols(self,segment:str="NFO",search:str|None=None)->Any:
        return await self.client.get_all_symbols(segment,search=search,allexpiry=False)
