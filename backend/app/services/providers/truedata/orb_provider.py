"""TrueData-native provider for ORB.

Historical bars construct the ORB. The option-chain API discovers contracts and
latest ticks refresh executable quotes. Advanced fields remain execution-quality
inputs; they do not alter the independent ORB alpha model.
"""
from __future__ import annotations
from datetime import date,datetime,timedelta,timezone
from typing import Any,Sequence
from app.engines.nifty_orb_options import Bar,OptionContract,StrategyConfig
from app.services.market_data.truedata import TrueDataHistoricalClient
from app.services.nifty_orb_option_chain import normalize_chain

class TrueDataOrbProvider:
    def __init__(self,client:TrueDataHistoricalClient)->None:self.client=client

    async def bars(self,symbol:str,cfg:StrategyConfig)->list[Bar]:
        interval=f"{cfg.interval_minutes}min"
        rows=await self.client.get_last_bars(symbol,200,interval=interval,bidask=0)
        out=[]
        for r in rows:
            raw=str(r.get("timestamp") or r.get("time") or "")
            dt=datetime.fromisoformat(raw.replace("Z","+00:00")) if "T" in raw else datetime.strptime(raw,"%Y-%m-%d %H:%M:%S")
            if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
            out.append(Bar(dt,float(r.get("open",0)),float(r.get("high",0)),float(r.get("low",0)),float(r.get("close",0)),float(r.get("volume",0))))
        return out

    async def latest_tick(self,symbol:str,*,bidask:bool=True)->dict[str,Any]|None:
        rows=await self.client.get_last_ticks(symbol,1,bidask=1 if bidask else 0)
        return rows[-1] if rows else None

    @staticmethod
    def _tick_time(tick:dict[str,Any])->datetime|None:
        raw=tick.get("timestamp") or tick.get("time")
        if not raw:return None
        try:
            if isinstance(raw,(int,float)):return datetime.fromtimestamp(float(raw)/1000,tz=timezone.utc)
            dt=datetime.fromisoformat(str(raw).replace("Z","+00:00"));return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError,ValueError,OverflowError):return None

    @staticmethod
    def _base_contracts(contracts:Sequence[OptionContract],cfg:StrategyConfig)->list[OptionContract]:
        today=date.today();out=[]
        for c in contracts:
            if not c.symbol or c.lot_size<=0 or c.ltp<=0:continue
            try:dte=(date.fromisoformat(c.expiry[:10])-today).days
            except ValueError:continue
            if dte<cfg.expiry_dte_min or dte>cfg.expiry_dte_max:continue
            out.append(c)
        return out

    async def refresh_contracts(self,contracts:Sequence[OptionContract],cfg:StrategyConfig)->list[OptionContract]:
        refreshed=[]
        for contract in self._base_contracts(contracts,cfg):
            tick=await self.latest_tick(contract.symbol,bidask=cfg.truedata_use_bid_ask) if cfg.truedata_use_ticks else None
            if cfg.truedata_use_ticks and tick is None:continue
            if tick:
                stamp=self._tick_time(tick)
                if cfg.truedata_use_quote_freshness and (stamp is None or max(0.0,(datetime.now(timezone.utc)-stamp).total_seconds())>cfg.max_quote_staleness_s):continue
                contract=OptionContract(contract.symbol,contract.strike,contract.expiry,contract.option_type,float(tick.get("ltp") or contract.ltp),float(tick.get("bid") or contract.bid),float(tick.get("ask") or contract.ask),contract.lot_size,contract.delta,float(tick.get("volume") or contract.volume),float(tick.get("oi") or contract.open_interest))
            if cfg.truedata_use_bid_ask and (contract.bid<=0 or contract.ask<contract.bid or contract.spread_pct>cfg.max_spread_pct):continue
            if contract.volume<cfg.min_option_volume:continue
            if cfg.truedata_use_oi and contract.open_interest<cfg.min_open_interest:continue
            refreshed.append(contract)
        return refreshed

    @staticmethod
    def _extract_expiries(payload:Any)->list[date]:
        values:set[date]=set()
        def visit(node:Any)->None:
            if isinstance(node,dict):
                for key,value in node.items():
                    if str(key).lower() in {"expiry","expiry_date","expirydate"}:
                        visit(value)
                    elif isinstance(value,(dict,list)):visit(value)
            elif isinstance(node,list):
                for value in node:visit(value)
            elif isinstance(node,str):
                text=node[:10]
                try:
                    values.add(date.fromisoformat(text))
                except ValueError:pass
        visit(payload);return sorted(d for d in values if d>=date.today())

    async def resolve_expiry(self,symbol:str,cfg:StrategyConfig)->str:
        payload=await self.client.get_all_symbols("NFO",search=symbol,allexpiry=True)
        expiries=self._extract_expiries(payload)
        if not expiries:raise ValueError(f"TrueData returned no eligible expiries for {symbol}")
        eligible=[d for d in expiries if cfg.expiry_dte_min<=(d-date.today()).days<=cfg.expiry_dte_max]
        if not eligible:raise ValueError(f"No TrueData expiry for {symbol} satisfies configured DTE range")
        if cfg.expiry_selection=="monthly":
            month_max=max(d for d in eligible if d.month==eligible[0].month) if any(d.month==eligible[0].month for d in eligible) else eligible[0]
            return month_max.isoformat()
        if cfg.expiry_selection=="weekly":
            weekly=[d for d in eligible if (d-date.today()).days<=7]
            return min(weekly or eligible).isoformat()
        return min(eligible).isoformat()

    async def option_chain(self,symbol:str,expiry:str,cfg:StrategyConfig)->list[OptionContract]:
        resolved=await self.resolve_expiry(symbol,cfg) if expiry in {"nearest","weekly","monthly",""} else expiry
        payload=await self.client.get_option_chain(symbol,resolved)
        return await self.refresh_contracts(normalize_chain(payload),cfg)

    async def symbols(self,segment:str="NFO",search:str|None=None)->Any:
        return await self.client.get_all_symbols(segment,search=search,allexpiry=False)
