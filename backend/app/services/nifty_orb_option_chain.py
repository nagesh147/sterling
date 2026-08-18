"""Normalize broker option-chain quotes for ORB option buying.

The ORB strategy consumes this boundary instead of knowing Kite/TrueData payload
shapes. No orders are placed here.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from typing import Any, Awaitable, Callable, Sequence
from app.engines.nifty_orb_options import OptionContract, StrategyConfig

@dataclass(frozen=True)
class ChainQuote:
    symbol: str
    strike: float
    expiry: str
    option_type: str
    ltp: float
    bid: float
    ask: float
    lot_size: int
    volume: float
    open_interest: float
    delta: float | None = None

    def to_contract(self) -> OptionContract:
        return OptionContract(self.symbol,self.strike,self.expiry,self.option_type,self.ltp,self.bid,self.ask,self.lot_size,self.delta,self.volume,self.open_interest)

def normalize_chain(rows: Sequence[dict[str, Any]] | dict[str, Any], *, default_lot_size: int = 1) -> list[OptionContract]:
    if isinstance(rows,dict):
        rows=rows.get("data") or rows.get("records") or rows.get("Records") or rows.get("options") or []
    result=[]
    for row in rows:
        raw_type=str(row.get("option_type") or row.get("instrument_type") or row.get("type") or "").upper()
        option_type={"CALL":"CE","C":"CE","PUT":"PE","P":"PE"}.get(raw_type,raw_type)
        if option_type not in {"CE","PE"}: continue
        try: strike=float(row.get("strike") or row.get("strike_price")); expiry=str(row.get("expiry") or row.get("expiry_date"))[:10]
        except (TypeError,ValueError): continue
        if strike<=0 or not expiry: continue
        result.append(ChainQuote(
            symbol=str(row.get("symbol") or row.get("tradingsymbol") or row.get("instrument") or ""),
            strike=strike,expiry=expiry,option_type=option_type,
            ltp=float(row.get("ltp") or row.get("last_price") or row.get("close") or 0),
            bid=float(row.get("bid") or row.get("bid_price") or 0),
            ask=float(row.get("ask") or row.get("ask_price") or 0),
            lot_size=int(row.get("lot_size") or row.get("lotsize") or default_lot_size),
            volume=float(row.get("volume") or 0),
            open_interest=float(row.get("open_interest") or row.get("oi") or 0),
            delta=float(row["delta"]) if row.get("delta") not in (None,"") else None,
        ).to_contract())
    return result


def filter_chain(contracts: Sequence[OptionContract], cfg: StrategyConfig, *, today: date | None = None) -> list[OptionContract]:
    today=today or date.today(); result=[]
    for contract in contracts:
        if not contract.symbol or contract.lot_size<=0 or contract.ltp<=0 or contract.bid<=0 or contract.ask<contract.bid: continue
        try: dte=(date.fromisoformat(contract.expiry[:10])-today).days
        except ValueError: continue
        if dte<cfg.expiry_dte_min or dte>cfg.expiry_dte_max: continue
        if contract.spread_pct>cfg.max_spread_pct: continue
        if contract.volume<cfg.min_option_volume or contract.open_interest<cfg.min_open_interest: continue
        result.append(contract)
    return result

QuoteFetcher=Callable[[str, str], Awaitable[Sequence[dict[str,Any]]]]

async def hydrate(symbol: str, direction: str, cfg: StrategyConfig, fetch_quotes: QuoteFetcher) -> list[OptionContract]:
    """Fetch, normalize and filter the CE/PE side required by one ORB signal."""
    option_type="CE" if direction=="LONG" else "PE"
    rows=await fetch_quotes(symbol,option_type)
    return filter_chain(normalize_chain(rows),cfg)
